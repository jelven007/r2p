use r2p::{IntoPyObject, IntoPyObjectRef};

#[derive(IntoPyObject, IntoPyObjectRef)]
struct Foo();
//~^ ERROR: cannot derive `IntoPyObject` for empty structs

#[derive(IntoPyObject, IntoPyObjectRef)]
struct Foo2 {}
//~^ ERROR: cannot derive `IntoPyObject` for empty structs

#[derive(IntoPyObject, IntoPyObjectRef)]
enum EmptyEnum {}
//~^ ERROR: cannot derive `IntoPyObject` for empty enum

#[derive(IntoPyObject, IntoPyObjectRef)]
enum EnumWithEmptyTupleVar {
    EmptyTuple(),
//~^ ERROR: cannot derive `IntoPyObject` for empty variants
    Valid(String),
}

#[derive(IntoPyObject, IntoPyObjectRef)]
enum EnumWithEmptyStructVar {
    EmptyStruct {},
//~^ ERROR: cannot derive `IntoPyObject` for empty variants
    Valid(String),
}

#[derive(IntoPyObject, IntoPyObjectRef)]
#[r2p(transparent)]
struct EmptyTransparentTup();
//~^ ERROR: cannot derive `IntoPyObject` for empty structs

#[derive(IntoPyObject, IntoPyObjectRef)]
#[r2p(transparent)]
struct EmptyTransparentStruct {}
//~^ ERROR: cannot derive `IntoPyObject` for empty structs

#[derive(IntoPyObject, IntoPyObjectRef)]
enum EnumWithTransparentEmptyTupleVar {
    #[r2p(transparent)]
    EmptyTuple(),
//~^ ERROR: cannot derive `IntoPyObject` for empty variants
    Valid(String),
}

#[derive(IntoPyObject, IntoPyObjectRef)]
enum EnumWithTransparentEmptyStructVar {
    #[r2p(transparent)]
    EmptyStruct {},
//~^ ERROR: cannot derive `IntoPyObject` for empty variants
    Valid(String),
}

#[derive(IntoPyObject, IntoPyObjectRef)]
#[r2p(transparent)]
struct TransparentTupTooManyFields(String, String);
//~^ ERROR: transparent structs and variants can only have 1 field

#[derive(IntoPyObject, IntoPyObjectRef)]
#[r2p(transparent)]
struct TransparentStructTooManyFields {
//~^ ERROR: transparent structs and variants can only have 1 field
    foo: String,
    bar: String,
}

#[derive(IntoPyObject, IntoPyObjectRef)]
enum EnumWithTransparentTupleTooMany {
    #[r2p(transparent)]
    EmptyTuple(String, String),
//~^ ERROR: transparent structs and variants can only have 1 field
    Valid(String),
}

#[derive(IntoPyObject, IntoPyObjectRef)]
enum EnumWithTransparentStructTooMany {
    #[r2p(transparent)]
    EmptyStruct {
//~^ ERROR: transparent structs and variants can only have 1 field
        foo: String,
        bar: String,
    },
    Valid(String),
}

#[derive(IntoPyObject, IntoPyObjectRef)]
#[r2p(unknown = "should not work")]
//~^ ERROR: expected one of: `transparent`, `from_item_all`, `annotation`, `crate`, `rename_all`
struct UnknownContainerAttr {
    a: String,
}

#[derive(IntoPyObject, IntoPyObjectRef)]
union Union {
//~^ ERROR: #[derive(`IntoPyObject`)] is not supported for unions
    a: usize,
}

#[derive(IntoPyObject, IntoPyObjectRef)]
enum UnitEnum {
    Unit,
//~^ ERROR: cannot derive `IntoPyObject` for empty variants
}

#[derive(IntoPyObject, IntoPyObjectRef)]
struct TupleAttribute(#[r2p(attribute)] String, usize);
//~^ ERROR: `item` and `attribute` are not permitted on tuple struct elements.

#[derive(IntoPyObject, IntoPyObjectRef)]
struct TupleItem(#[r2p(item)] String, usize);
//~^ ERROR: `item` and `attribute` are not permitted on tuple struct elements.

#[derive(IntoPyObject, IntoPyObjectRef)]
struct StructAttribute {
    #[r2p(attribute)]
    foo: String,
}

#[derive(IntoPyObject, IntoPyObjectRef)]
#[r2p(transparent)]
struct StructTransparentItem {
    #[r2p(item)]
//~^ ERROR: `transparent` structs may not have `item` nor `attribute` for the inner field
    foo: String,
}

#[derive(IntoPyObject)]
#[r2p(transparent)]
struct StructTransparentIntoPyWith {
    #[r2p(into_py_with = into)]
//~^ ERROR: `into_py_with` is not permitted on `transparent` structs or variants
    foo: String,
}

#[derive(IntoPyObjectRef)]
#[r2p(transparent)]
struct StructTransparentIntoPyWithRef {
    #[r2p(into_py_with = into_ref)]
//~^ ERROR: `into_py_with` is not permitted on `transparent` structs or variants
    foo: String,
}

#[derive(IntoPyObject)]
#[r2p(transparent)]
struct TupleTransparentIntoPyWith(#[r2p(into_py_with = into)] String);
//~^ ERROR: `into_py_with` is not permitted on `transparent` structs

#[derive(IntoPyObject)]
enum EnumTupleIntoPyWith {
    TransparentTuple(#[r2p(into_py_with = into)] usize),
//~^ ERROR: `into_py_with` is not permitted on `transparent` structs
}

#[derive(IntoPyObject)]
enum EnumStructIntoPyWith {
    #[r2p(transparent)]
    TransparentStruct {
        #[r2p(into_py_with = into)]
//~^ ERROR: `into_py_with` is not permitted on `transparent` structs or variants
        a: usize,
    },
}

#[derive(IntoPyObject, IntoPyObjectRef)]
#[r2p(transparent, rename_all = "camelCase")]
//~^ ERROR: `rename_all` is not permitted on `transparent` structs and variants
struct StructTransparentRenameAll {
    foo_bar: String,
}

#[derive(IntoPyObject, IntoPyObjectRef)]
#[r2p(rename_all = "camelCase")]
//~^ ERROR: `rename_all` is useless on tuple structs and variants.
struct StructTupleRenameAll(String, usize);

#[derive(IntoPyObject, IntoPyObjectRef)]
enum EnumTransparentVariantRenameAll {
    #[r2p(rename_all = "camelCase")]
//~^ ERROR: `rename_all` is not permitted on `transparent` structs and variants
    #[r2p(transparent)]
    Variant { foo: String },
}

#[derive(IntoPyObject, IntoPyObjectRef)]
enum EnumTupleVariantRenameAll {
    #[r2p(rename_all = "camelCase")]
//~^ ERROR: `rename_all` is useless on tuple structs and variants.
    Variant(String, usize),
}

#[derive(IntoPyObject, IntoPyObjectRef)]
#[r2p(rename_all = "camelCase")]
//~^ ERROR: `rename_all` is not supported at top level for enums
enum EnumTopRenameAll {
    Variant { foo: String },
}

fn main() {}
