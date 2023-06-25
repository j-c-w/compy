import glob
import os
import json
import random
import subprocess
import sys
import traceback

import pandas as pd
from tqdm import tqdm

from compy.datasets import dataset
from compy.representations.extractors import ClangDriver


class PolybenchDataset(dataset.Dataset):
    def __init__(self):
        super().__init__()

        uri = "https://kumisystems.dl.sourceforge.net/project/polybench/polybench-c-4.2.1-beta.tar.gz"
        self.download_http_and_extract(uri)
        self.content_dir = os.path.join(self.content_dir, 'polybench-c-4.2.1-beta')

        self.programming_language = ClangDriver.ProgrammingLanguage.C
        self.additional_include_dirs = []
        self.compiler_flags = []

    def get_size(self):
        return 1

    def preprocess(self, builder, visitor, start_at=False, num_samples=None, randomly_select_samples=False):
        filenames = []
        for subdir in ['datamining', 'stencils', 'linear-algebra', 'medley']:
            filenames += glob.glob(os.path.join(self.content_dir, subdir) + '/**/*.c', recursive=True)
        filenames = [f for f in filenames if 'Nussinov.orig.c' not in f]

        samples = []
        for filename in tqdm(filenames, desc="Source Code -> IR+ -> Code rep in %s" % self.content_dir):
            includes = [(os.path.join(self.content_dir, 'utilities'), ClangDriver.IncludeDirType.User),
                        (os.path.dirname(filename), ClangDriver.IncludeDirType.User)]
            flags = []

            clang_driver = ClangDriver(
                ClangDriver.ProgrammingLanguage.CPlusPlus,
                ClangDriver.OptimizationLevel.O3,
                includes,
                flags,
            )

            builder.clang_driver = clang_driver
            with open(filename, "rb") as file:
                source_code = file.read()
            extractionInfo = builder.string_to_info(source_code)
            for functionInfo in extractionInfo.functionInfos:
                meta = {'filename': filename}
                sample = builder.info_to_representation(functionInfo, visitor, meta)
