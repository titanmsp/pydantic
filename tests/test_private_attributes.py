import functools
from enum import Enum
from typing import ClassVar, Generic, Optional, TypeVar

import pytest
from pydantic_core import PydanticUndefined

from pydantic import BaseModel, ConfigDict, PrivateAttr, computed_field
from pydantic.fields import ModelPrivateAttr


def test_private_attribute():
    default = {'a': {}}

    class Model(BaseModel):
        _foo = PrivateAttr(default)

    assert set(Model.__private_attributes__) == {'_foo'}

    m = Model()
    assert m._foo == default
    assert m._foo is not default
    assert m._foo['a'] is not default['a']

    m._foo = None
    assert m._foo is None

    assert m.model_dump() == {}
    assert m.__dict__ == {}


def test_private_attribute_double_leading_underscore():
    default = {'a': {}}

    class Model(BaseModel):
        __foo = PrivateAttr(default)

    assert set(Model.__private_attributes__) == {'_Model__foo'}

    m = Model()

    with pytest.raises(AttributeError, match='__foo'):
        m.__foo
    assert m._Model__foo == default
    assert m._Model__foo is not default
    assert m._Model__foo['a'] is not default['a']

    m._Model__foo = None
    assert m._Model__foo is None

    assert m.model_dump() == {}
    assert m.__dict__ == {}


def test_private_attribute_nested():
    class SubModel(BaseModel):
        _foo = PrivateAttr(42)
        x: int

    class Model(BaseModel):
        y: int
        sub: SubModel

    m = Model(y=1, sub={'x': 2})
    assert m.sub._foo == 42


def test_private_attribute_factory():
    default = {'a': {}}

    def factory():
        return default

    class Model(BaseModel):
        _foo = PrivateAttr(default_factory=factory)

    assert Model.__private_attributes__ == {'_foo': PrivateAttr(default_factory=factory)}

    m = Model()
    assert m._foo == default
    assert m._foo is default
    assert m._foo['a'] is default['a']

    m._foo = None
    assert m._foo is None

    assert m.model_dump() == {}
    assert m.__dict__ == {}


def test_private_attribute_annotation():
    class Model(BaseModel):
        """The best model"""

        _foo: str

    assert Model.__private_attributes__ == {'_foo': PrivateAttr(PydanticUndefined)}
    assert repr(Model.__doc__) == "'The best model'"

    m = Model()
    with pytest.raises(AttributeError):
        m._foo

    m._foo = '123'
    assert m._foo == '123'

    m._foo = None
    assert m._foo is None

    del m._foo

    with pytest.raises(AttributeError):
        m._foo

    m._foo = '123'
    assert m._foo == '123'

    assert m.model_dump() == {}
    assert m.__dict__ == {}


def test_underscore_attrs_are_private():
    class Model(BaseModel):
        _foo: str = 'abc'
        _bar: ClassVar[str] = 'cba'

    assert Model._bar == 'cba'
    assert Model.__private_attributes__ == {'_foo': PrivateAttr('abc')}

    m = Model()
    assert m._foo == 'abc'
    m._foo = None
    assert m._foo is None

    with pytest.raises(
        AttributeError,
        match=(
            "'_bar' is a ClassVar of `Model` and cannot be set on an instance. "
            'If you want to set a value on the class, use `Model._bar = value`.'
        ),
    ):
        m._bar = 1


def test_private_attribute_intersection_with_extra_field():
    class Model(BaseModel):
        _foo = PrivateAttr('private_attribute')

        model_config = ConfigDict(extra='allow')

    assert set(Model.__private_attributes__) == {'_foo'}
    m = Model(_foo='field')
    assert m._foo == 'private_attribute'
    assert m.__dict__ == {}
    assert m.__pydantic_extra__ == {'_foo': 'field'}
    assert m.model_dump() == {'_foo': 'field'}

    m._foo = 'still_private'
    assert m._foo == 'still_private'
    assert m.__dict__ == {}
    assert m.__pydantic_extra__ == {'_foo': 'field'}
    assert m.model_dump() == {'_foo': 'field'}


def test_private_attribute_invalid_name():
    with pytest.raises(
        NameError,
        match="Private attributes must not use valid field names; use sunder names, e.g. '_foo' instead of 'foo'.",
    ):

        class Model(BaseModel):
            foo = PrivateAttr()


def test_slots_are_ignored():
    class Model(BaseModel):
        __slots__ = (
            'foo',
            '_bar',
        )

        def __init__(self):
            super().__init__()
            for attr_ in self.__slots__:
                object.__setattr__(self, attr_, 'spam')

    assert Model.__private_attributes__ == {}
    assert set(Model.__slots__) == {'foo', '_bar'}
    m1 = Model()
    m2 = Model()

    for attr in Model.__slots__:
        assert object.__getattribute__(m1, attr) == 'spam'

    # In v2, you are always allowed to set instance attributes if the name starts with `_`.
    m1._bar = 'not spam'
    assert m1._bar == 'not spam'
    assert m2._bar == 'spam'

    with pytest.raises(ValueError, match='"Model" object has no field "foo"'):
        m1.foo = 'not spam'


def test_default_and_default_factory_used_error():
    with pytest.raises(TypeError, match='cannot specify both default and default_factory'):
        PrivateAttr(default=123, default_factory=lambda: 321)


def test_config_override_init():
    class MyModel(BaseModel):
        x: str
        _private_attr: int

        def __init__(self, **data) -> None:
            super().__init__(**data)
            self._private_attr = 123

    m = MyModel(x='hello')
    assert m.model_dump() == {'x': 'hello'}
    assert m._private_attr == 123


def test_generic_private_attribute():
    T = TypeVar('T')

    class Model(BaseModel, Generic[T]):
        value: T
        _private_value: T

    m = Model[int](value=1, _private_attr=3)
    m._private_value = 3
    assert m.model_dump() == {'value': 1}


def test_private_attribute_multiple_inheritance():
    # We need to test this since PrivateAttr uses __slots__ and that has some restrictions with regards to
    # multiple inheritance
    default = {'a': {}}

    class GrandParentModel(BaseModel):
        _foo = PrivateAttr(default)

    class ParentAModel(GrandParentModel):
        pass

    class ParentBModel(GrandParentModel):
        _bar = PrivateAttr(default)

    class Model(ParentAModel, ParentBModel):
        _baz = PrivateAttr(default)

    assert GrandParentModel.__private_attributes__ == {
        '_foo': PrivateAttr(default),
    }
    assert ParentBModel.__private_attributes__ == {
        '_foo': PrivateAttr(default),
        '_bar': PrivateAttr(default),
    }
    assert Model.__private_attributes__ == {
        '_foo': PrivateAttr(default),
        '_bar': PrivateAttr(default),
        '_baz': PrivateAttr(default),
    }

    m = Model()
    assert m._foo == default
    assert m._foo is not default
    assert m._foo['a'] is not default['a']

    assert m._bar == default
    assert m._bar is not default
    assert m._bar['a'] is not default['a']

    assert m._baz == default
    assert m._baz is not default
    assert m._baz['a'] is not default['a']

    m._foo = None
    assert m._foo is None

    m._bar = None
    assert m._bar is None

    m._baz = None
    assert m._baz is None

    assert m.model_dump() == {}
    assert m.__dict__ == {}


def test_private_attributes_not_dunder() -> None:
    with pytest.raises(
        NameError,
        match="Private attributes must not use dunder names; use a single underscore prefix instead of '__foo__'.",
    ):

        class MyModel(BaseModel):
            __foo__ = PrivateAttr({'private'})


def test_ignored_types_are_ignored() -> None:
    class IgnoredType:
        pass

    class MyModel(BaseModel):
        model_config = ConfigDict(ignored_types=(IgnoredType,))

        _a = IgnoredType()
        _b: int = IgnoredType()
        _c: IgnoredType
        _d: IgnoredType = IgnoredType()

        # The following are included to document existing behavior, which is to make them into PrivateAttrs
        # this can be updated if the current behavior is not the desired behavior
        _e: int
        _f: int = 1
        _g = 1

    assert sorted(MyModel.__private_attributes__.keys()) == ['_e', '_f', '_g']


@pytest.mark.skipif(not hasattr(functools, 'cached_property'), reason='cached_property is not available')
def test_ignored_types_are_ignored_cached_property():
    """Demonstrate the members of functools are ignore here as with fields."""

    class MyModel(BaseModel):
        _a: functools.cached_property
        _b: int

    assert set(MyModel.__private_attributes__) == {'_b'}


def test_none_as_private_attr():
    from pydantic import BaseModel

    class A(BaseModel):
        _x: None

    a = A()
    a._x = None
    assert a._x is None


def test_layout_compatible_multiple_private_parents():
    import typing as t

    import pydantic

    class ModelMixin(pydantic.BaseModel):
        _mixin_private: t.Optional[str] = pydantic.PrivateAttr(None)

    class Model(pydantic.BaseModel):
        public: str = 'default'
        _private: t.Optional[str] = pydantic.PrivateAttr(None)

    class NewModel(ModelMixin, Model):
        pass

    assert set(NewModel.__private_attributes__) == {'_mixin_private', '_private'}
    m = NewModel()
    m._mixin_private = 1
    m._private = 2

    assert m.__pydantic_private__ == {'_mixin_private': 1, '_private': 2}
    assert m._mixin_private == 1
    assert m._private == 2


def test_unannotated_private_attr():
    from pydantic import BaseModel, PrivateAttr

    class A(BaseModel):
        _x = PrivateAttr()
        _y = 52

    a = A()
    assert a._y == 52
    assert a.__pydantic_private__ == {'_y': 52}
    a._x = 1
    assert a.__pydantic_private__ == {'_x': 1, '_y': 52}


def test_classvar_collision_prevention(create_module):
    module = create_module(
        # language=Python
        """
from __future__ import annotations

from pydantic import BaseModel
import typing as t

class BaseConfig(BaseModel):
    _FIELD_UPDATE_STRATEGY: t.ClassVar[t.dict[str, t.Any]] = {}
"""
    )

    assert module.BaseConfig._FIELD_UPDATE_STRATEGY == {}


@pytest.mark.skipif(not hasattr(functools, 'cached_property'), reason='cached_property is not available')
def test_private_properties_not_included_in_iter_cached_property() -> None:
    class Model(BaseModel):
        foo: int

        @computed_field
        @functools.cached_property
        def _foo(self) -> int:
            return -self.foo

    m = Model(foo=1)
    assert '_foo' not in list(k for k, _ in m)


def test_private_properties_not_included_in_iter_property() -> None:
    class Model(BaseModel):
        foo: int

        @computed_field
        @property
        def _foo(self) -> int:
            return -self.foo

    m = Model(foo=1)
    assert '_foo' not in list(k for k, _ in m)


def test_private_properties_not_included_in_repr_by_default_property() -> None:
    class Model(BaseModel):
        foo: int

        @computed_field
        @property
        def _private_property(self) -> int:
            return -self.foo

    m = Model(foo=1)
    m_repr = repr(m)
    assert '_private_property' not in m_repr


@pytest.mark.skipif(not hasattr(functools, 'cached_property'), reason='cached_property is not available')
def test_private_properties_not_included_in_repr_by_default_cached_property() -> None:
    class Model(BaseModel):
        foo: int

        @computed_field
        @functools.cached_property
        def _private_cached_property(self) -> int:
            return -self.foo

    m = Model(foo=1)
    m_repr = repr(m)
    assert '_private_cached_property' not in m_repr


@pytest.mark.parametrize('base', [ModelPrivateAttr, object])
@pytest.mark.parametrize('use_annotation', [True, False])
def test_private_descriptors(base, use_annotation):
    set_name_calls = []
    get_calls = []
    set_calls = []
    delete_calls = []

    class MyDescriptor(base):
        def __init__(self, fn):
            super().__init__()
            self.fn = fn
            self.name = ''

        def __set_name__(self, owner, name):
            set_name_calls.append((owner, name))
            self.name = name

        def __get__(self, obj, type=None):
            get_calls.append((obj, type))
            return self.fn(obj) if obj else self

        def __set__(self, obj, value):
            set_calls.append((obj, value))
            self.fn = lambda obj: value

        def __delete__(self, obj):
            delete_calls.append(obj)

            def fail(obj):
                # I have purposely not used the exact formatting you'd get if the attribute wasn't defined,
                # to make it clear this function is being called, while also having sensible behavior
                raise AttributeError(f'{self.name!r} is not defined on {obj!r}')

            self.fn = fail

    class A(BaseModel):
        x: int

        if use_annotation:
            _some_func: MyDescriptor = MyDescriptor(lambda self: self.x)
        else:
            _some_func = MyDescriptor(lambda self: self.x)

        @property
        def _double_x(self):
            return self.x * 2

    assert set(A.__private_attributes__) == {'_some_func'}
    assert set_name_calls == [(A, '_some_func')]

    a = A(x=2)

    assert a._double_x == 4  # Ensure properties with leading underscores work fine and don't become private attributes

    assert get_calls == []
    assert a._some_func == 2
    assert get_calls == [(a, A)]

    assert set_calls == []
    a._some_func = 3
    assert set_calls == [(a, 3)]

    assert a._some_func == 3
    assert get_calls == [(a, A), (a, A)]

    assert delete_calls == []
    del a._some_func
    assert delete_calls == [a]

    with pytest.raises(AttributeError, match=r"'_some_func' is not defined on A\(x=2\)"):
        a._some_func
    assert get_calls == [(a, A), (a, A), (a, A)]


def test_private_attr_set_name():
    class SetNameInt(int):
        _owner_attr_name: Optional[str] = None

        def __set_name__(self, owner, name):
            self._owner_attr_name = f'{owner.__name__}.{name}'

    _private_attr_default = SetNameInt(1)

    class Model(BaseModel):
        _private_attr_1: int = PrivateAttr(default=_private_attr_default)
        _private_attr_2: SetNameInt = SetNameInt(2)

    assert _private_attr_default._owner_attr_name == 'Model._private_attr_1'

    m = Model()
    assert m._private_attr_1 == 1
    assert m._private_attr_1._owner_attr_name == 'Model._private_attr_1'
    assert m._private_attr_2 == 2
    assert m._private_attr_2._owner_attr_name == 'Model._private_attr_2'


def test_private_attribute_similar_classnames() -> None:
    class Fullname(str, Enum):
        pass

    class Full(BaseModel):
        _priv: object = Fullname

    assert isinstance(Full._priv, ModelPrivateAttr)


def test_private_attr_default_descriptor_attribute_error():
    class SetNameInt(int):
        def __get__(self, obj, cls):
            return self

    _private_attr_default = SetNameInt(1)

    class Model(BaseModel):
        _private_attr: int = PrivateAttr(default=_private_attr_default)

    assert Model.__private_attributes__['_private_attr'].__get__(None, Model) == _private_attr_default

    with pytest.raises(AttributeError, match="'ModelPrivateAttr' object has no attribute 'some_attr'"):
        Model.__private_attributes__['_private_attr'].some_attr


def test_private_attr_set_name_do_not_crash_if_not_callable():
    class SetNameInt(int):
        __set_name__ = None

    _private_attr_default = SetNameInt(2)

    class Model(BaseModel):
        _private_attr: int = PrivateAttr(default=_private_attr_default)

    # Checks below are just to ensure that everything is the same as in `test_private_attr_set_name`
    # The main check is that model class definition above doesn't crash
    assert Model()._private_attr == 2
