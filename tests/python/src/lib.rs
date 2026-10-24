use r2p::prelude::*;
use r2p::types::PyDict;

#[cfg(feature = "experimental-inspect")]
mod annotations;
mod awaitable;
mod buf_and_str;
mod comparisons;
mod consts;
#[cfg(not(Py_LIMITED_API))]
mod datetime;
mod dict_iter;
mod enums;
mod exception;
mod misc;
mod objstore;
mod othermod;
#[cfg(wip_feature_std)]
mod path;
mod pyclasses;
mod pyfunctions;
mod sequence;
mod subclassing;

#[doc = include_str!("../MODULE_DOC.md")]
#[pymodule]
mod r2p_pytests {
    use super::*;

    #[cfg(any(not(Py_LIMITED_API), Py_3_11))]
    #[pymodule_export]
    use buf_and_str::buf_and_str;

    #[cfg(not(Py_LIMITED_API))]
    #[pymodule_export]
    use datetime::datetime;

    #[cfg(wip_feature_std)]
    #[pymodule_export]
    use path::path;

    #[cfg(not(wip_feature_std))]
    #[pymodule_export]
    use path;

    #[pymodule_export]
    use {
        awaitable::awaitable, comparisons::comparisons, consts::consts, dict_iter::dict_iter,
        enums::enums, exception::exception, misc::misc, objstore::objstore, othermod::othermod,
        pyclasses::pyclasses, pyfunctions::pyfunctions, sequence::sequence,
        subclassing::subclassing,
    };

    #[cfg(feature = "experimental-inspect")]
    #[pymodule_export]
    use annotations::annotations;

    #[pymodule_export]
    const NO_STD: bool = cfg!(not(wip_feature_std));

    // Inserting to sys.modules allows importing submodules nicely from Python
    // e.g. import r2p_pytests.buf_and_str as bas
    #[pymodule_init]
    fn init(m: &Bound<'_, PyModule>) -> PyResult<()> {
        let sys = PyModule::import(m.py(), "sys")?;
        let sys_modules = sys.getattr("modules")?.cast_into::<PyDict>()?;
        #[cfg(feature = "experimental-inspect")]
        sys_modules.set_item("r2p_pytests.annotations", m.getattr("annotations")?)?;
        sys_modules.set_item("r2p_pytests.awaitable", m.getattr("awaitable")?)?;
        #[cfg(any(not(Py_LIMITED_API), Py_3_11))]
        sys_modules.set_item("r2p_pytests.buf_and_str", m.getattr("buf_and_str")?)?;
        sys_modules.set_item("r2p_pytests.comparisons", m.getattr("comparisons")?)?;
        sys_modules.set_item("r2p_pytests.consts", m.getattr("consts")?)?;
        #[cfg(not(Py_LIMITED_API))]
        sys_modules.set_item("r2p_pytests.datetime", m.getattr("datetime")?)?;
        sys_modules.set_item("r2p_pytests.dict_iter", m.getattr("dict_iter")?)?;
        sys_modules.set_item("r2p_pytests.enums", m.getattr("enums")?)?;
        sys_modules.set_item("r2p_pytests.exception", m.getattr("exception")?)?;
        sys_modules.set_item("r2p_pytests.misc", m.getattr("misc")?)?;
        sys_modules.set_item("r2p_pytests.objstore", m.getattr("objstore")?)?;
        sys_modules.set_item("r2p_pytests.othermod", m.getattr("othermod")?)?;
        sys_modules.set_item("r2p_pytests.path", m.getattr("path")?)?;
        sys_modules.set_item("r2p_pytests.pyclasses", m.getattr("pyclasses")?)?;
        sys_modules.set_item("r2p_pytests.pyfunctions", m.getattr("pyfunctions")?)?;
        sys_modules.set_item("r2p_pytests.sequence", m.getattr("sequence")?)?;
        sys_modules.set_item("r2p_pytests.subclassing", m.getattr("subclassing")?)?;

        Ok(())
    }
}

#[cfg(not(wip_feature_std))]
#[pymodule]
mod path {}
