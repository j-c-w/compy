import glob
import os
import random
import traceback

import pandas as pd
from tqdm import tqdm

from compy.datasets import dataset
from compy.representations.extractors import ClangDriver


def get_all_src_files(content_dir):
    ret = []
    for root, dirs, files in os.walk(content_dir):
        for file in files:
            if file.endswith('.c'):
                ret.append(os.path.join(root, file))
    return ret


class LivermorecDataset(dataset.Dataset):
    def __init__(self, name, domain):
        super().__init__(name)
        self.domain = domain

        uri = "https://www.netlib.org/benchmark/livermorec"
        self.download_http(uri)

        self.programming_language = ClangDriver.ProgrammingLanguage.C
        self.additional_include_dirs = []
        self.compiler_flags = ['-Wno-return-type']

    def get_size(self):
        return 1

    def get_invocations(self):
        return [True]

    def preprocess(self, builder, visitor, invocations=None):
        if not invocations:
            return None
        filenames = get_all_src_files(self.content_dir)
        filename = filenames[0]
        with open(filename, "rb") as f:
            source_code = f.read()

#        try:
        extractionInfo = builder.string_to_info(source_code)
        for functionInfo in extractionInfo.functionInfos:
            meta = {'dataset_name': 'livermorec', 'filename': filename}
            sample = builder.info_to_representation(functionInfo, visitor, meta)

#        except Exception as e:
#            print('WARNING: Exception occurred while preprocessing sample')
#            print(traceback.format_exc())

        return {
            "samples": [
                {
                    "info": "livermorec",
                    "x": {"code_rep": sample},
                }
            ],
        }
