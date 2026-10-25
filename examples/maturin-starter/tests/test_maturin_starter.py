from maturin_starter import ExampleClass, PythonClass


def test_divide() -> None:
    import pytest
    from maturin_starter import divide

    assert divide(84, 2) == 42
    for numerator, denominator in ((1, 0), (-(2**31), -1)):
        with pytest.raises(ValueError, match="division by zero or integer overflow"):
            divide(numerator, denominator)
    assert divide(6, 2) == 3


def test_python_class() -> None:
    py_class = PythonClass(value=10)
    assert py_class.value == 10


def test_example_class() -> None:
    example = ExampleClass(value=11)
    assert example.value == 11


def test_doc() -> None:
    import maturin_starter

    assert maturin_starter.__doc__ == "An example module implemented in Rust using r2p."
