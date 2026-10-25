use crate::model::{
    Argument, Arguments, Attribute, Class, Constant, Expr, Function, Module, Operator,
    VariableLengthArgument,
};
use anyhow::{Context, Result, anyhow, bail, ensure};
use goblin::Object;
use goblin::elf::program_header::PT_LOAD;
use goblin::elf::section_header::SHN_UNDEF;
use goblin::elf::{Elf, Sym};
use goblin::mach::symbols::{N_SECT, NO_SECT};
use goblin::mach::{Mach, MachO, SingleArch};
use goblin::pe::PE;
use serde::{Deserialize, Serialize};
use std::borrow::Cow;
use std::cmp::Ordering;
use std::collections::{HashMap, HashSet};
use std::io::Read;
use std::path::Path;
use std::{fs, str};

// Bound allocation before reading, deserializing, or recursively expanding metadata.
const MAX_BINARY_BYTES: u64 = 512 * 1024 * 1024;
const MAX_CHUNK_BYTES: usize = 1024 * 1024;
const MAX_METADATA_BYTES: usize = 64 * 1024 * 1024;
const MAX_CHUNKS: usize = 16_384;
const MAX_STRUCTURE_NODES: usize = 65_536;
const MAX_DEPTH: usize = 64;

/// Introspect a cdylib built with r2p and returns the definition of a Python module.
///
/// This function currently supports ELF (most *nix including Linux), Mach-O (macOS) and PE (Windows).
///
/// Inputs are limited to 512 MiB per binary, 1 MiB per chunk, 64 MiB of metadata,
/// 16,384 chunks, 65,536 JSON nodes per chunk and expanded members, and 64 levels
/// of nesting. Expanded metadata (serialized bytes times containment depth) is
/// conservatively limited to 64 MiB. Invalid offsets, duplicate IDs and
/// containment cycles return errors.
pub fn introspect_cdylib(library_path: impl AsRef<Path>, main_module_name: &str) -> Result<Module> {
    let chunks = find_introspection_chunks_in_binary_object(library_path.as_ref())?;
    parse_chunks(&chunks, main_module_name)
}

/// Parses the introspection chunks found in the binary
fn parse_chunks(chunks: &[Chunk], main_module_name: &str) -> Result<Module> {
    ensure!(
        chunks.len() <= MAX_CHUNKS,
        "Introspection chunk count exceeds limit"
    );
    let mut chunks_by_id = HashMap::<&str, &Chunk>::new();
    let mut chunks_by_parent = HashMap::<&str, Vec<&Chunk>>::new();
    for chunk in chunks {
        let (id, parent) = match chunk {
            Chunk::Module { id, .. } => (Some(id.as_str()), None),
            Chunk::Class { id, parent, .. } => (Some(id.as_str()), parent.as_deref()),
            Chunk::Function { id, parent, .. } | Chunk::Attribute { id, parent, .. } => {
                (id.as_deref(), parent.as_deref())
            }
        };
        if let Some(id) = id {
            ensure!(
                chunks_by_id.insert(id, chunk).is_none(),
                "Duplicate introspection ID: {id}"
            );
        }
        if let Some(parent) = parent {
            chunks_by_parent.entry(parent).or_default().push(chunk);
        }
    }
    validate_containment(chunks, &chunks_by_id, &chunks_by_parent)?;
    ensure!(
        chunks
            .iter()
            .filter(|chunk| matches!(chunk, Chunk::Module { name, .. } if name == main_module_name))
            .count()
            <= 1,
        "Multiple root modules named {main_module_name}"
    );
    // We look for the root chunk
    for chunk in chunks {
        if let Chunk::Module {
            id,
            name,
            members,
            doc,
            incomplete,
        } = chunk
        {
            if name == main_module_name {
                let type_hint_for_annotation_id = introspection_id_to_type_hint_for_root_module(
                    chunk,
                    &chunks_by_id,
                    &chunks_by_parent,
                );
                return convert_module(
                    id,
                    name,
                    members,
                    *incomplete,
                    doc.as_deref(),
                    &chunks_by_id,
                    &chunks_by_parent,
                    &type_hint_for_annotation_id,
                );
            }
        }
    }
    bail!("No module named {main_module_name} found")
}

/// Check the entire graph iteratively, before either recursive conversion pass.
/// Memoized subtree costs also bound repeated expansion of shared DAG members.
fn validate_containment<'a>(
    chunks: &'a [Chunk],
    chunks_by_id: &HashMap<&'a str, &'a Chunk>,
    chunks_by_parent: &HashMap<&str, Vec<&Chunk>>,
) -> Result<()> {
    let mut edges = HashMap::<&str, Vec<&str>>::new();
    let mut sizes = HashMap::<&str, usize>::new();
    let weights = chunks
        .iter()
        .map(|chunk| Ok((chunk as *const Chunk, serde_json::to_vec(chunk)?.len())))
        .collect::<Result<HashMap<_, _>>>()?;
    let mut bytes_by_id = HashMap::<&str, usize>::new();
    let mut own_bytes = HashMap::<&str, usize>::new();
    let mut edge_count = 0usize;
    for chunk in chunks {
        let (id, members) = match chunk {
            Chunk::Module { id, members, .. } => (id.as_str(), members.as_slice()),
            Chunk::Class { id, .. } => (id.as_str(), [].as_slice()),
            _ => continue,
        };
        let children = chunks_by_parent
            .get(id)
            .into_iter()
            .flatten()
            .copied()
            .chain(
                members
                    .iter()
                    .filter_map(|member| chunks_by_id.get(member.as_str()).copied()),
            );
        let mut container_children = Vec::new();
        let mut size = 1usize;
        let mut bytes = weights[&(chunk as *const Chunk)];
        own_bytes.insert(id, bytes);
        for child in children {
            size += 1;
            bytes = bytes.saturating_add(weights[&(child as *const Chunk)]);
            edge_count += 1;
            ensure!(
                edge_count <= MAX_STRUCTURE_NODES,
                "Introspection member count exceeds limit"
            );
            if let Chunk::Module { id, .. } | Chunk::Class { id, .. } = child {
                container_children.push(id.as_str());
            }
        }
        edges.insert(id, container_children);
        sizes.insert(id, size);
        bytes_by_id.insert(id, bytes);
    }
    let mut visiting = HashSet::new();
    let mut completed = HashMap::<&str, (usize, usize, usize)>::new();
    for chunk in chunks {
        let (Chunk::Module { id, .. } | Chunk::Class { id, .. }) = chunk else {
            continue;
        };
        let mut stack = vec![(id.as_str(), false)];
        while let Some((id, finish)) = stack.pop() {
            if completed.contains_key(id) {
                continue;
            }
            if !finish {
                ensure!(
                    visiting.insert(id),
                    "Introspection containment cycle at ID: {id}"
                );
                stack.push((id, true));
                stack.extend(edges[id].iter().rev().map(|child| (*child, false)));
            } else {
                let mut depth = 1;
                let mut size = sizes[id];
                let mut bytes = bytes_by_id[id];
                for child in &edges[id] {
                    let (child_depth, child_size, child_bytes) = completed[child];
                    depth = depth.max(child_depth + 1);
                    size = size.saturating_add(child_size - 1);
                    bytes = bytes.saturating_add(child_bytes - own_bytes[child]);
                }
                ensure!(
                    depth <= MAX_DEPTH,
                    "Introspection containment depth exceeds limit"
                );
                ensure!(
                    size <= MAX_STRUCTURE_NODES,
                    "Introspection expanded member count exceeds limit"
                );
                ensure!(
                    bytes.saturating_mul(depth) <= MAX_METADATA_BYTES,
                    "Introspection expanded metadata size exceeds limit"
                );
                visiting.remove(id);
                completed.insert(id, (depth, size, bytes));
            }
        }
    }
    Ok(())
}

#[expect(clippy::too_many_arguments)]
fn convert_module(
    id: &str,
    name: &str,
    members: &[String],
    mut incomplete: bool,
    docstring: Option<&str>,
    chunks_by_id: &HashMap<&str, &Chunk>,
    chunks_by_parent: &HashMap<&str, Vec<&Chunk>>,
    type_hint_for_annotation_id: &HashMap<String, Expr>,
) -> Result<Module> {
    let mut member_chunks = chunks_by_parent
        .get(&id)
        .into_iter()
        .flatten()
        .copied()
        .collect::<Vec<_>>();
    for member in members {
        if let Some(c) = chunks_by_id.get(member.as_str()) {
            member_chunks.push(*c);
        } else {
            incomplete = true; // We don't find an element
        }
    }
    let (modules, classes, functions, attributes) = convert_members(
        member_chunks,
        chunks_by_id,
        chunks_by_parent,
        type_hint_for_annotation_id,
    )?;

    Ok(Module {
        name: name.into(),
        modules,
        classes,
        functions,
        attributes,
        incomplete,
        docstring: docstring.map(Into::into),
    })
}

type Members = (Vec<Module>, Vec<Class>, Vec<Function>, Vec<Attribute>);

/// Convert a list of members of a module or a class
fn convert_members<'a>(
    chunks: impl IntoIterator<Item = &'a Chunk>,
    chunks_by_id: &HashMap<&str, &Chunk>,
    chunks_by_parent: &HashMap<&str, Vec<&Chunk>>,
    type_hint_for_annotation_id: &HashMap<String, Expr>,
) -> Result<Members> {
    let mut modules = Vec::new();
    let mut classes = Vec::new();
    let mut functions = Vec::new();
    let mut attributes = Vec::new();
    for chunk in chunks {
        match chunk {
            Chunk::Module {
                name,
                id,
                members,
                incomplete,
                doc,
            } => {
                modules.push(convert_module(
                    id,
                    name,
                    members,
                    *incomplete,
                    doc.as_deref(),
                    chunks_by_id,
                    chunks_by_parent,
                    type_hint_for_annotation_id,
                )?);
            }
            Chunk::Class {
                name,
                id,
                bases,
                decorators,
                doc,
                parent: _,
            } => classes.push(convert_class(
                id,
                name,
                bases,
                decorators,
                doc.as_deref(),
                chunks_by_id,
                chunks_by_parent,
                type_hint_for_annotation_id,
            )?),
            Chunk::Function {
                name,
                id: _,
                arguments,
                parent: _,
                decorators,
                is_async,
                returns,
                doc,
            } => functions.push(convert_function(
                name,
                arguments,
                decorators,
                returns,
                *is_async,
                doc.as_deref(),
                type_hint_for_annotation_id,
            )),
            Chunk::Attribute {
                name,
                id: _,
                parent: _,
                value,
                annotation,
                doc,
            } => attributes.push(convert_attribute(
                name,
                value,
                annotation,
                doc.as_deref(),
                type_hint_for_annotation_id,
            )),
        }
    }
    // We sort elements to get a stable output
    modules.sort_by(|l, r| l.name.cmp(&r.name));
    classes.sort_by(|l, r| l.name.cmp(&r.name));
    functions.sort_by(|l, r| match l.name.cmp(&r.name) {
        Ordering::Equal => {
            fn decorator_expr_key(expr: &Expr) -> (u32, Cow<'_, str>) {
                // We put plain names before attributes for @property to be before @foo.property
                match expr {
                    Expr::Name { id, .. } => (0, Cow::Borrowed(id)),
                    Expr::Attribute { value, attr } => {
                        let (c, v) = decorator_expr_key(value);
                        (c + 1, Cow::Owned(format!("{v}.{attr}")))
                    }
                    _ => (0, Cow::Borrowed("")), // We don't care
                }
            }
            // We pick an ordering based on decorators
            l.decorators
                .iter()
                .map(decorator_expr_key)
                .cmp(r.decorators.iter().map(decorator_expr_key))
        }
        o => o,
    });
    attributes.sort_by(|l, r| l.name.cmp(&r.name));
    Ok((modules, classes, functions, attributes))
}

#[expect(clippy::too_many_arguments)]
fn convert_class(
    id: &str,
    name: &str,
    bases: &[ChunkExpr],
    decorators: &[ChunkExpr],
    docstring: Option<&str>,
    chunks_by_id: &HashMap<&str, &Chunk>,
    chunks_by_parent: &HashMap<&str, Vec<&Chunk>>,
    type_hint_for_annotation_id: &HashMap<String, Expr>,
) -> Result<Class> {
    let (nested_modules, nested_classes, methods, attributes) = convert_members(
        chunks_by_parent.get(&id).into_iter().flatten().copied(),
        chunks_by_id,
        chunks_by_parent,
        type_hint_for_annotation_id,
    )?;
    ensure!(
        nested_modules.is_empty(),
        "Classes cannot contain nested modules"
    );
    Ok(Class {
        name: name.into(),
        bases: bases
            .iter()
            .map(|e| convert_expr(e, type_hint_for_annotation_id))
            .collect(),
        methods,
        attributes,
        decorators: decorators
            .iter()
            .map(|e| convert_expr(e, type_hint_for_annotation_id))
            .collect(),
        inner_classes: nested_classes,
        docstring: docstring.map(Into::into),
    })
}

fn convert_function(
    name: &str,
    arguments: &ChunkArguments,
    decorators: &[ChunkExpr],
    returns: &Option<ChunkExpr>,
    is_async: bool,
    docstring: Option<&str>,
    type_hint_for_annotation_id: &HashMap<String, Expr>,
) -> Function {
    Function {
        name: name.into(),
        decorators: decorators
            .iter()
            .map(|e| convert_expr(e, type_hint_for_annotation_id))
            .collect(),
        arguments: Arguments {
            positional_only_arguments: arguments
                .posonlyargs
                .iter()
                .map(|a| convert_argument(a, type_hint_for_annotation_id))
                .collect(),
            arguments: arguments
                .args
                .iter()
                .map(|a| convert_argument(a, type_hint_for_annotation_id))
                .collect(),
            vararg: arguments
                .vararg
                .as_ref()
                .map(|a| convert_variable_length_argument(a, type_hint_for_annotation_id)),
            keyword_only_arguments: arguments
                .kwonlyargs
                .iter()
                .map(|e| convert_argument(e, type_hint_for_annotation_id))
                .collect(),
            kwarg: arguments
                .kwarg
                .as_ref()
                .map(|a| convert_variable_length_argument(a, type_hint_for_annotation_id)),
        },
        returns: returns
            .as_ref()
            .map(|a| convert_expr(a, type_hint_for_annotation_id)),
        is_async,
        docstring: docstring.map(Into::into),
    }
}

fn convert_argument(
    arg: &ChunkArgument,
    type_hint_for_annotation_id: &HashMap<String, Expr>,
) -> Argument {
    Argument {
        name: arg.name.clone(),
        default_value: arg
            .default
            .as_ref()
            .map(|e| convert_expr(e, type_hint_for_annotation_id)),
        annotation: arg
            .annotation
            .as_ref()
            .map(|a| convert_expr(a, type_hint_for_annotation_id)),
    }
}

fn convert_variable_length_argument(
    arg: &ChunkArgument,
    type_hint_for_annotation_id: &HashMap<String, Expr>,
) -> VariableLengthArgument {
    VariableLengthArgument {
        name: arg.name.clone(),
        annotation: arg
            .annotation
            .as_ref()
            .map(|a| convert_expr(a, type_hint_for_annotation_id)),
    }
}

fn convert_attribute(
    name: &str,
    value: &Option<ChunkExpr>,
    annotation: &Option<ChunkExpr>,
    docstring: Option<&str>,
    type_hint_for_annotation_id: &HashMap<String, Expr>,
) -> Attribute {
    Attribute {
        name: name.into(),
        value: value
            .as_ref()
            .map(|v| convert_expr(v, type_hint_for_annotation_id)),
        annotation: annotation
            .as_ref()
            .map(|a| convert_expr(a, type_hint_for_annotation_id)),
        docstring: docstring.map(ToString::to_string),
    }
}

fn convert_expr(expr: &ChunkExpr, type_hint_for_annotation_id: &HashMap<String, Expr>) -> Expr {
    match expr {
        ChunkExpr::Name { id } => Expr::Name { id: id.clone() },
        ChunkExpr::Attribute { value, attr } => Expr::Attribute {
            value: Box::new(convert_expr(value, type_hint_for_annotation_id)),
            attr: attr.clone(),
        },
        ChunkExpr::BinOp { left, op, right } => Expr::BinOp {
            left: Box::new(convert_expr(left, type_hint_for_annotation_id)),
            op: match op {
                ChunkOperator::BitOr => Operator::BitOr,
            },
            right: Box::new(convert_expr(right, type_hint_for_annotation_id)),
        },
        ChunkExpr::Subscript { value, slice } => Expr::Subscript {
            value: Box::new(convert_expr(value, type_hint_for_annotation_id)),
            slice: Box::new(convert_expr(slice, type_hint_for_annotation_id)),
        },
        ChunkExpr::Tuple { elts } => Expr::Tuple {
            elts: elts
                .iter()
                .map(|e| convert_expr(e, type_hint_for_annotation_id))
                .collect(),
        },
        ChunkExpr::List { elts } => Expr::List {
            elts: elts
                .iter()
                .map(|e| convert_expr(e, type_hint_for_annotation_id))
                .collect(),
        },
        ChunkExpr::Constant { value } => Expr::Constant {
            value: match value {
                ChunkConstant::None => Constant::None,
                ChunkConstant::Bool { value } => Constant::Bool(*value),
                ChunkConstant::Int { value } => Constant::Int(value.clone()),
                ChunkConstant::Float { value } => Constant::Float(value.clone()),
                ChunkConstant::Str { value } => Constant::Str(value.clone()),
                ChunkConstant::Ellipsis => Constant::Ellipsis,
            },
        },
        ChunkExpr::Id { id } => {
            if let Some(expr) = type_hint_for_annotation_id.get(id) {
                expr.clone()
            } else {
                // This is a pyclass not exposed, we fallback to Any
                Expr::Attribute {
                    value: Box::new(Expr::Name {
                        id: "typing".into(),
                    }),
                    attr: "Any".to_string(),
                }
            }
        }
    }
}

/// Returns the type hint for each class introspection id defined in the module and its submodule
fn introspection_id_to_type_hint_for_root_module(
    module_chunk: &Chunk,
    chunks_by_id: &HashMap<&str, &Chunk>,
    chunks_by_parent: &HashMap<&str, Vec<&Chunk>>,
) -> HashMap<String, Expr> {
    fn add_introspection_id_to_type_hint_for_module_members(
        module_id: &str,
        module_full_name: &str,
        module_members: &[String],
        chunks_by_id: &HashMap<&str, &Chunk>,
        chunks_by_parent: &HashMap<&str, Vec<&Chunk>>,
        output: &mut HashMap<String, Expr>,
    ) {
        for member in chunks_by_parent
            .get(&module_id)
            .into_iter()
            .flatten()
            .chain(
                module_members
                    .iter()
                    .filter_map(|id| chunks_by_id.get(id.as_str())),
            )
            .copied()
        {
            match member {
                Chunk::Module {
                    name, id, members, ..
                } => {
                    add_introspection_id_to_type_hint_for_module_members(
                        id,
                        &format!("{}.{}", module_full_name, name),
                        members,
                        chunks_by_id,
                        chunks_by_parent,
                        output,
                    );
                }
                Chunk::Class { id, name, .. } => {
                    output.insert(
                        id.clone(),
                        Expr::Attribute {
                            value: Box::new(Expr::Name {
                                id: module_full_name.into(),
                            }),
                            attr: name.clone(),
                        },
                    );
                    add_introspection_id_to_type_hint_for_class_subclasses(
                        id,
                        name,
                        module_full_name,
                        chunks_by_parent,
                        output,
                    );
                }
                _ => (),
            }
        }
    }

    fn add_introspection_id_to_type_hint_for_class_subclasses(
        class_id: &str,
        class_name: &str,
        class_module: &str,
        chunks_by_parent: &HashMap<&str, Vec<&Chunk>>,
        output: &mut HashMap<String, Expr>,
    ) {
        for member in chunks_by_parent.get(&class_id).into_iter().flatten() {
            if let Chunk::Class { id, name, .. } = member {
                let class_name = format!("{}.{}", class_name, name);
                add_introspection_id_to_type_hint_for_class_subclasses(
                    id,
                    &class_name,
                    class_module,
                    chunks_by_parent,
                    output,
                );
                output.insert(
                    id.clone(),
                    Expr::Attribute {
                        value: Box::new(Expr::Name {
                            id: class_module.into(),
                        }),
                        attr: class_name,
                    },
                );
            }
        }
    }

    let mut output = HashMap::new();
    let Chunk::Module {
        id, name, members, ..
    } = module_chunk
    else {
        unreachable!("The chunk must be a module")
    };
    add_introspection_id_to_type_hint_for_module_members(
        id,
        name,
        members,
        chunks_by_id,
        chunks_by_parent,
        &mut output,
    );
    output
}

fn find_introspection_chunks_in_binary_object(path: &Path) -> Result<Vec<Chunk>> {
    let file =
        fs::File::open(path).with_context(|| format!("Failed to read {}", path.display()))?;
    ensure!(
        file.metadata()?.len() <= MAX_BINARY_BYTES,
        "Binary size exceeds introspection limit"
    );
    let mut library_content = Vec::new();
    // A bounded read also covers files which grow after the metadata check.
    file.take(MAX_BINARY_BYTES + 1)
        .read_to_end(&mut library_content)?;
    ensure!(
        library_content.len() as u64 <= MAX_BINARY_BYTES,
        "Binary size exceeds introspection limit"
    );
    find_introspection_chunks_in_binary_content(&library_content)
}

fn find_introspection_chunks_in_binary_content(library_content: &[u8]) -> Result<Vec<Chunk>> {
    ensure!(
        library_content.len() as u64 <= MAX_BINARY_BYTES,
        "Binary size exceeds introspection limit"
    );
    match Object::parse(library_content)
        .context("The built library is not valid or not supported by our binary parser")?
    {
        Object::Elf(elf) => find_introspection_chunks_in_elf(&elf, library_content),
        Object::Mach(Mach::Binary(macho)) => {
            find_introspection_chunks_in_macho(&macho, library_content)
        }
        Object::Mach(Mach::Fat(multi_arch)) => {
            for (arch, fat_arch) in multi_arch.into_iter().zip(multi_arch.iter_arches()) {
                match arch? {
                    SingleArch::MachO(macho) => {
                        // Mach-O offsets are relative to the beginning of the architecture slice
                        return find_introspection_chunks_in_macho(
                            &macho,
                            fat_arch?.slice(library_content),
                        );
                    }
                    SingleArch::Archive(_) => (),
                }
            }
            bail!("No Mach-o chunk found in the multi-arch Mach-o container")
        }
        Object::PE(pe) => find_introspection_chunks_in_pe(&pe, library_content),
        other => {
            bail!("Only ELF, Mach-o and PE containers can be introspected, got {other:?}")
        }
    }
}

fn find_introspection_chunks_in_elf(elf: &Elf<'_>, library_content: &[u8]) -> Result<Vec<Chunk>> {
    // The introspection symbols are exported, so they are in the dynamic symbol table that
    // survives stripping. We also look at the full symbol table, if present, to support
    // binaries where they are not exported.
    let symbols = elf
        .dynsyms
        .iter()
        .map(|sym| (sym, elf.dynstrtab.get_at(sym.st_name)))
        .chain(
            elf.syms
                .iter()
                .map(|sym| (sym, elf.strtab.get_at(sym.st_name))),
        );
    let mut seen_names = HashSet::new();
    let mut chunks = ChunkCollector::default();
    for (sym, sym_name) in symbols {
        let Some(sym_name) = sym_name else {
            continue;
        };
        if !is_introspection_symbol(sym_name)
            || sym.st_shndx == SHN_UNDEF as usize
            || !seen_names.insert(sym_name)
        {
            continue;
        }
        let data_offset = elf_symbol_file_offset(elf, &sym).with_context(|| {
            format!("Failed to locate the introspection symbol {sym_name} in the ELF file")
        })?;
        chunks.push(
            sym_name,
            library_content
                .get(data_offset..)
                .context("The introspection symbol is outside of the ELF file")?,
            elf.little_endian,
        )?;
    }
    Ok(chunks.chunks)
}

/// Maps the virtual address of a symbol to its offset in the file using the loadable segments.
///
/// We use program headers and not section headers because the latter are optional.
fn elf_symbol_file_offset(elf: &Elf<'_>, sym: &Sym) -> Result<usize> {
    let address = sym.st_value;
    let segment = elf
        .program_headers
        .iter()
        .find(|header| {
            header.p_type == PT_LOAD
                && header.p_vaddr <= address
                && address - header.p_vaddr < header.p_filesz
        })
        .with_context(|| {
            format!("No loadable segment with file content contains the address {address:#x}")
        })?;
    segment
        .p_offset
        .checked_add(address - segment.p_vaddr)
        .and_then(|offset| usize::try_from(offset).ok())
        .context("File offset overflow")
}

fn find_introspection_chunks_in_macho(
    macho: &MachO<'_>,
    library_content: &[u8],
) -> Result<Vec<Chunk>> {
    if !macho.little_endian {
        bail!("Only little endian Mach-o binaries are supported");
    }

    let sections = macho
        .segments
        .sections()
        .flatten()
        .map(|t| t.map(|s| s.0))
        .collect::<Result<Vec<_>, _>>()?;
    let mut chunks = ChunkCollector::default();
    for symbol in macho.symbols() {
        let (name, nlist) = symbol?;
        if nlist.is_global()
            && nlist.get_type() == N_SECT
            && nlist.n_sect != NO_SECT as usize
            && is_introspection_symbol(name)
        {
            let section = sections
                .get(nlist.n_sect - 1) // Sections are counted from 1
                .context("The introspection symbol section does not exist")?;
            let data_offset = nlist
                .n_value
                .checked_sub(section.addr)
                .filter(|offset| *offset < section.size)
                .and_then(|offset| offset.checked_add(section.offset.into()))
                .context("The introspection symbol is outside of its section")?;
            chunks.push(
                name,
                library_content
                    .get(usize::try_from(data_offset).context("File offset overflow")?..)
                    .context("The introspection symbol is outside of the Mach-O file")?,
                macho.little_endian,
            )?;
        }
    }
    Ok(chunks.chunks)
}

fn find_introspection_chunks_in_pe(pe: &PE<'_>, library_content: &[u8]) -> Result<Vec<Chunk>> {
    let mut chunks = ChunkCollector::default();
    for export in &pe.exports {
        if is_introspection_symbol(export.name.unwrap_or_default()) {
            chunks.push(
                export.name.unwrap_or_default(),
                library_content
                    .get(export.offset.context("No symbol offset")?..)
                    .context("The introspection symbol is outside of the PE file")?,
                true,
            )?;
        }
    }
    Ok(chunks.chunks)
}

#[derive(Default)]
struct ChunkCollector {
    chunks: Vec<Chunk>,
    bytes: usize,
}

impl ChunkCollector {
    fn push(&mut self, name: &str, content: &[u8], little_endian: bool) -> Result<()> {
        ensure!(
            self.chunks.len() < MAX_CHUNKS,
            "Introspection chunk count exceeds limit"
        );
        let payload = chunk_payload(name, content, little_endian)?;
        self.bytes = self.bytes.saturating_add(payload.len());
        ensure!(
            self.bytes <= MAX_METADATA_BYTES,
            "Introspection metadata size exceeds limit"
        );
        self.chunks.push(deserialize_payload(payload)?);
        Ok(())
    }
}

#[cfg(test)]
fn deserialize_chunk(
    symbol_name: &str,
    content_with_chunk_at_the_beginning: &[u8],
    is_little_endian: bool,
) -> Result<Chunk> {
    deserialize_payload(chunk_payload(
        symbol_name,
        content_with_chunk_at_the_beginning,
        is_little_endian,
    )?)
}

fn chunk_payload<'a>(
    symbol_name: &str,
    content: &'a [u8],
    is_little_endian: bool,
) -> Result<&'a [u8]> {
    let symbol_version = introspection_symbol_version(symbol_name).unwrap_or_default();
    ensure!(
        symbol_version == "1",
        "The introspection format version '{symbol_version}' is not supported by this version of r2p-introspection. Please upgrade your build tool like maturin or downgrade r2p"
    );

    let length = content
        .get(..4)
        .and_then(|length| length.try_into().ok())
        .context("The introspection chunk must contain a length")?;
    let length = if is_little_endian {
        u32::from_le_bytes(length)
    } else {
        u32::from_be_bytes(length)
    };
    ensure!(
        length as usize <= MAX_CHUNK_BYTES,
        "Introspection chunk size exceeds limit"
    );
    let end = 4usize
        .checked_add(length as usize)
        .context("Introspection chunk length overflow")?;
    content.get(4..end).ok_or_else(|| {
        anyhow!("The introspection chunk length {length} is greater than the binary size")
    })
}

fn deserialize_payload(chunk: &[u8]) -> Result<Chunk> {
    let value: serde_json::Value = serde_json::from_slice(chunk).with_context(|| {
        format!(
            "Failed to parse introspection chunk (first 160 bytes): {:?}",
            String::from_utf8_lossy(&chunk[..chunk.len().min(160)])
        )
    })?;
    let mut stack = vec![(&value, 1usize)];
    let mut count = 0;
    while let Some((node, depth)) = stack.pop() {
        count += 1;
        ensure!(
            count <= MAX_STRUCTURE_NODES,
            "Introspection JSON node count exceeds limit"
        );
        ensure!(depth <= MAX_DEPTH, "Introspection JSON depth exceeds limit");
        match node {
            serde_json::Value::Array(items) => stack.extend(items.iter().map(|v| (v, depth + 1))),
            serde_json::Value::Object(items) => {
                stack.extend(items.values().map(|v| (v, depth + 1)))
            }
            _ => (),
        }
    }
    serde_json::from_value(value).context("Invalid introspection chunk structure")
}

fn is_introspection_symbol(name: &str) -> bool {
    introspection_symbol_version(name).is_some()
}

fn introspection_symbol_version(name: &str) -> Option<&str> {
    let name = name
        .strip_prefix('_')
        .unwrap_or(name)
        .strip_prefix("R2P_INTROSPECTION_")?;
    Some(name.split_once('_').unwrap_or((name, "")).0)
}

#[derive(Deserialize, Serialize)]
#[serde(tag = "type", rename_all = "lowercase")]
enum Chunk {
    Module {
        id: String,
        name: String,
        members: Vec<String>,
        #[serde(default)]
        doc: Option<String>,
        #[serde(default)]
        incomplete: bool,
    },
    Class {
        id: String,
        name: String,
        #[serde(default)]
        bases: Vec<ChunkExpr>,
        #[serde(default)]
        decorators: Vec<ChunkExpr>,
        #[serde(default)]
        parent: Option<String>,
        #[serde(default)]
        doc: Option<String>,
    },
    Function {
        #[serde(default)]
        id: Option<String>,
        name: String,
        arguments: Box<ChunkArguments>,
        #[serde(default)]
        parent: Option<String>,
        #[serde(default)]
        decorators: Vec<ChunkExpr>,
        #[serde(default)]
        returns: Option<ChunkExpr>,
        #[serde(default, rename = "async")]
        is_async: bool,
        #[serde(default)]
        doc: Option<String>,
    },
    Attribute {
        #[serde(default)]
        id: Option<String>,
        #[serde(default)]
        parent: Option<String>,
        name: String,
        #[serde(default)]
        value: Option<ChunkExpr>,
        #[serde(default)]
        annotation: Option<ChunkExpr>,
        #[serde(default)]
        doc: Option<String>,
    },
}

#[derive(Deserialize, Serialize)]
struct ChunkArguments {
    #[serde(default)]
    posonlyargs: Vec<ChunkArgument>,
    #[serde(default)]
    args: Vec<ChunkArgument>,
    #[serde(default)]
    vararg: Option<ChunkArgument>,
    #[serde(default)]
    kwonlyargs: Vec<ChunkArgument>,
    #[serde(default)]
    kwarg: Option<ChunkArgument>,
}

#[derive(Deserialize, Serialize)]
struct ChunkArgument {
    name: String,
    #[serde(default)]
    default: Option<ChunkExpr>,
    #[serde(default)]
    annotation: Option<ChunkExpr>,
}

#[derive(Deserialize, Serialize)]
#[serde(tag = "type", rename_all = "lowercase")]
enum ChunkExpr {
    /// A constant like `None` or `123`
    Constant {
        #[serde(flatten)]
        value: ChunkConstant,
    },
    /// A name
    Name { id: String },
    /// An attribute `value.attr`
    Attribute { value: Box<Self>, attr: String },
    /// A binary operator
    BinOp {
        left: Box<Self>,
        op: ChunkOperator,
        right: Box<Self>,
    },
    /// A tuple
    Tuple { elts: Vec<Self> },
    /// A list
    List { elts: Vec<Self> },
    /// A subscript `value[slice]`
    Subscript { value: Box<Self>, slice: Box<Self> },
    /// An introspection id
    Id { id: String },
}

#[derive(Deserialize, Serialize)]
#[serde(tag = "kind", rename_all = "lowercase")]
pub enum ChunkConstant {
    None,
    Bool { value: bool },
    Int { value: String },
    Float { value: String },
    Str { value: String },
    Ellipsis,
}

#[derive(Deserialize, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum ChunkOperator {
    BitOr,
}

#[cfg(test)]
mod tests;
