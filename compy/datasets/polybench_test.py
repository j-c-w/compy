import pytest

from compy.datasets import PolybenchDataset
from compy.representations import RepresentationBuilder


class objectview(object):
    def __init__(self, d):
        self.__dict__ = d


class TestBuilder(RepresentationBuilder):
    def string_to_info(self, src):
        functionInfo = objectview({"name": "xyz"})
        return objectview({"functionInfos": [functionInfo]})

    def info_to_representation(self, info, visitor):
        return "Repr"


@pytest.fixture
def polybench_fixture():
    ds = PolybenchDataset()
    yield ds


def test_preprocess(polybench_fixture):
    builder = TestBuilder()
    polybench_fixture.preprocess(builder, None)
