use super::*;
use goblin::elf::{header::Header, program_header::ProgramHeader};

fn module(id: impl Into<String>, members: Vec<String>) -> Chunk {
    Chunk::Module {
        id: id.into(),
        name: "root".into(),
        members,
        incomplete: false,
        doc: None,
    }
}

fn payload(json: &[u8], little_endian: bool) -> Vec<u8> {
    let length = u32::try_from(json.len()).unwrap();
    let mut bytes = if little_endian {
        length.to_le_bytes().to_vec()
    } else {
        length.to_be_bytes().to_vec()
    };
    bytes.extend_from_slice(json);
    bytes
}

fn error<T>(result: Result<T>) -> String {
    match result {
        Ok(_) => panic!("Expected malformed input to fail"),
        Err(err) => format!("{err:#}"),
    }
}

#[test]
fn chunk_endianness_and_truncation() {
    let json = br#"{"type":"module","id":"root","name":"root","members":[]}"#;
    for little in [false, true] {
        let bytes = payload(json, little);
        assert!(deserialize_chunk("R2P_INTROSPECTION_1_TEST", &bytes, little).is_ok());
        for end in 0..bytes.len() {
            assert!(deserialize_chunk("R2P_INTROSPECTION_1_TEST", &bytes[..end], little).is_err());
        }
    }
}

#[test]
fn version_structure_and_diagnostic_limits() {
    assert!(error(deserialize_chunk("R2P_INTROSPECTION_2_X", &[], true)).contains("not supported"));
    assert!(
        error(deserialize_chunk(
            "R2P_INTROSPECTION_1_X",
            &u32::MAX.to_le_bytes(),
            true
        ))
        .contains("size exceeds")
    );
    assert!(error(deserialize_payload(br#"{"type":"module"}"#)).contains("Invalid introspection"));
    let invalid = vec![b'x'; MAX_CHUNK_BYTES];
    assert!(error(deserialize_payload(&invalid)).len() < 512);
}

#[test]
fn json_depth_and_width_limits() {
    let nested = format!("{}0{}", "[".repeat(MAX_DEPTH), "]".repeat(MAX_DEPTH));
    assert!(error(deserialize_payload(nested.as_bytes())).contains("JSON depth"));
    let wide = format!("[{}0]", "0,".repeat(MAX_STRUCTURE_NODES));
    assert!(error(deserialize_payload(wide.as_bytes())).contains("JSON node count"));
}

#[test]
fn duplicate_ids_and_ambiguous_roots_fail() {
    assert!(
        error(parse_chunks(
            &[module("a", vec![]), module("a", vec![])],
            "root"
        ))
        .contains("Duplicate")
    );
    assert!(
        error(parse_chunks(
            &[module("a", vec![]), module("b", vec![])],
            "root"
        ))
        .contains("Multiple root")
    );
}

#[test]
fn missing_members_remain_incomplete() {
    let result = parse_chunks(&[module("root", vec!["missing".into()])], "root").unwrap();
    assert!(result.incomplete);
}

#[test]
fn member_and_parent_cycles_fail() {
    let self_cycle = [module("root", vec!["root".into()])];
    assert!(error(parse_chunks(&self_cycle, "root")).contains("cycle"));
    let mutual = [module("a", vec!["b".into()]), module("b", vec!["a".into()])];
    assert!(error(parse_chunks(&mutual, "root")).contains("cycle"));
    let classes = ["a", "b"].map(|id| Chunk::Class {
        id: id.into(),
        name: id.into(),
        bases: vec![],
        decorators: vec![],
        parent: Some(if id == "a" { "b" } else { "a" }.into()),
        doc: None,
    });
    assert!(error(parse_chunks(&classes, "root")).contains("cycle"));
}

#[test]
fn containment_depth_and_expansion_limits() {
    let chain = (0..=MAX_DEPTH)
        .map(|i| {
            let mut chunk = module(
                i.to_string(),
                if i < MAX_DEPTH {
                    vec![(i + 1).to_string()]
                } else {
                    vec![]
                },
            );
            if let Chunk::Module { name, .. } = &mut chunk {
                *name = i.to_string();
            }
            chunk
        })
        .collect::<Vec<_>>();
    assert!(error(parse_chunks(&chain, "0")).contains("depth exceeds"));
    assert!(parse_chunks(&chain[1..], "1").is_ok());
    let shared = (0..20)
        .map(|i| {
            module(
                i.to_string(),
                if i < 19 {
                    vec![(i + 1).to_string(); 2]
                } else {
                    vec![]
                },
            )
        })
        .collect::<Vec<_>>();
    assert!(error(parse_chunks(&shared, "root")).contains("expanded"));
    let mut big = module("big", vec![]);
    if let Chunk::Module { doc, .. } = &mut big {
        *doc = Some("d".repeat(MAX_CHUNK_BYTES / 2));
    }
    let repeated = [module("root", vec!["big".into(); 128]), big];
    assert!(error(parse_chunks(&repeated, "root")).contains("expanded metadata"));
}

#[test]
fn chunk_and_total_metadata_limits() {
    let chunks = (0..=MAX_CHUNKS)
        .map(|i| module(i.to_string(), vec![]))
        .collect::<Vec<_>>();
    assert!(error(parse_chunks(&chunks, "root")).contains("chunk count"));
    let bytes = payload(
        br#"{"type":"module","id":"root","name":"root","members":[]}"#,
        true,
    );
    let mut collector = ChunkCollector {
        bytes: MAX_METADATA_BYTES,
        ..Default::default()
    };
    assert!(error(collector.push("R2P_INTROSPECTION_1_X", &bytes, true)).contains("metadata size"));
    collector.bytes = 0;
    collector.chunks = chunks;
    assert!(error(collector.push("R2P_INTROSPECTION_1_X", &bytes, true)).contains("chunk count"));
}

#[test]
fn elf_offsets_reject_missing_segments_and_overflow() {
    let mut elf = Elf::lazy_parse(Header::new(goblin::container::Ctx::default())).unwrap();
    let mut symbol = Sym {
        st_value: 8,
        ..Default::default()
    };
    assert!(error(elf_symbol_file_offset(&elf, &symbol)).contains("No loadable segment"));
    elf.program_headers.push(ProgramHeader {
        p_type: PT_LOAD,
        p_offset: u64::MAX,
        p_vaddr: 0,
        p_filesz: 16,
        ..Default::default()
    });
    assert!(error(elf_symbol_file_offset(&elf, &symbol)).contains("overflow"));
    elf.program_headers[0].p_offset = 4;
    assert_eq!(elf_symbol_file_offset(&elf, &symbol).unwrap(), 12);
    symbol.st_value = 16;
    assert!(elf_symbol_file_offset(&elf, &symbol).is_err());
}

#[test]
fn oversized_file_is_rejected_before_reading() {
    let path = std::env::temp_dir().join(format!("r2p-introspection-limit-{}", std::process::id()));
    let file = fs::File::create(&path).unwrap();
    file.set_len(MAX_BINARY_BYTES + 1).unwrap();
    let result = introspect_cdylib(&path, "root");
    fs::remove_file(path).unwrap();
    assert!(error(result).contains("Binary size"));
}

#[test]
fn bounded_binary_and_chunk_mutations_do_not_panic() {
    let mut state = 0x5eed_u64;
    let magics: &[&[u8]] = &[b"\x7fELF", b"MZ", b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe"];
    for i in 0..4096 {
        let mut bytes = vec![0; i % 512];
        for byte in &mut bytes {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            *byte = state as u8;
        }
        if bytes.len() >= 4 {
            let magic = magics[i % magics.len()];
            bytes[..magic.len()].copy_from_slice(magic);
        }
        let _ = find_introspection_chunks_in_binary_content(&bytes);
        let _ = deserialize_chunk("R2P_INTROSPECTION_1_FUZZ", &bytes, i % 2 == 0);
    }
}
