#[r2p::pymodule]
mod mymodule {
    #[r2p::pymodule(submodule)]
    mod submod {}
    //~^ ERROR: `submodule` may only be specified once (it is implicitly always specified for nested modules)
}

fn main() {}
