import os
import multiprocessing
import pickle
import sys
import os.path
import itertools

import sqlite3
import pandas as pd
import tqdm
import numpy
from absl import app
from absl import flags
from typing import Mapping

from compy.datasets import GeneralDataset
from compy.datasets import LivermorecDataset
from compy.representations.extractors.extractors import Visitor
from compy.representations.ast_graphs import ASTCodeBuilder
from compy.representations.ast_graphs import ASTCodeVisitor
from compy.representations.extractors import ClangDriver
from compy.utils import flatten_dict


sys.setrecursionlimit(100000)

flags.DEFINE_string('out_dir', None, 'Output directory.')
flags.DEFINE_bool('debug', False, 'Single-process mode for debugging.')
FLAGS = flags.FLAGS

datasets = [
  # LivermorecDataset(),
  GeneralDataset('https://github.com/libav/libav.git', 'libav'),
  GeneralDataset('https://github.com/mirror/x264.git', 'x264'),
  GeneralDataset('https://github.com/ImageMagick/ImageMagick.git', 'ImageMagick'),
  GeneralDataset('https://github.com/WinMerge/freeimage.git', 'freeimage'),
  GeneralDataset('https://github.com/DentonW/DevIL.git', 'DevIL', 'DevIL'),
  GeneralDataset('https://github.com/FFmpeg/FFmpeg.git', 'ffmpeg'),
  # GeneralDataset('https://github.com/opencv/opencv.git', 'opencv'),
]

def store(data, filename):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    # Save
    with open(filename, "wb") as f:
        pickle.dump(data, f)


def get_files(path, prefix=None, suffix=None):
    filenames = []
    for root, dirs, files in os.walk(path):
        for file in files:
            ok = False
            if prefix:
                if not file.startswith(prefix):
                    continue
            if suffix:
                if not file.endswith(suffix):
                    continue
            filenames.append(os.path.join(root, file))

    return filenames


class MultiProcessedTask(object):
    def __init__(self, base_dir, num_processes, num_tasks, previous_task, verbose):
        self.base_dir = base_dir
        self.num_processes = num_processes
        self.num_tasks = num_tasks
        self.previous_task = previous_task
        self.verbose = verbose

        self.in_dir = self.previous_task.out_dir if self.previous_task else None
        self.out_dir = os.path.join(self.base_dir, self.__get_tasks_str())

    def run(self):
        # Load all tasks and split them up
        tasks = self._load_tasks()
        tasks_split = self.split(tasks, self.num_tasks)
        tasks_split_indexed = [(i, s) for i, s in enumerate(tasks_split)]

        # Run the splits
        if FLAGS.debug:
            # - In the same process
            list(map(self._process_tasks, tasks_split_indexed))
        else:
            # - In a multiprocessing pool
            with multiprocessing.Pool(processes=self.num_processes) as pool:
                list(tqdm.tqdm(pool.imap(self._process_tasks,
                                         tasks_split_indexed), total=len(tasks_split_indexed),
                               desc="Processing %s" % self.__class__.__name__))

    def _process_tasks(self, indexed_tasks: list):
        tasks_idx, tasks = indexed_tasks
        for task_idx, task in tqdm.tqdm(enumerate(tasks),
                                        desc="Processing %s %d" % (self.__class__.__name__, tasks_idx),
                                        disable=not self.verbose):
            self._process_task(task, tasks_idx)

    def _load_tasks(self):
        raise NotImplemented

    def _process_task(self, tasks: list, tasks_idx: str):
        raise NotImplemented

    def split(self, a, n):
        k, m = divmod(len(a), n)
        return list(a[i*k+min(i, m):(i+1)*k+min(i+1, m)] for i in range(n))

    def __get_tasks_str(self):
        tasks = [self.__class__.__name__]

        it = self.previous_task
        while it:
            tasks.append(it.__class__.__name__)
            it = it.previous_task
        tasks.reverse()

        return '_'.join(tasks)

    def __repr__(self):
        return self.__class__.__name__ + ": " + str(self.__dict__)


class ExtractTask(MultiProcessedTask):
    def __init__(self, base_dir, num_processes, num_tasks, previous_task=None, verbose=False):
        super().__init__(base_dir, num_processes, num_tasks, previous_task, verbose)

    def _load_tasks(self):
        ds_and_invocations = []
        for ds in datasets:
            for invocation in ds.get_invocations():
                ds_and_invocations.append((ds, invocation))
        return ds_and_invocations

    def _process_tasks(self, indexed_tasks):
        task_idx, tasks = indexed_tasks

        # If debug, print output directly to console. If not, write to log files
        if not FLAGS.debug:
            self.__enable_file_logging(task_idx)

        samples = self.extract_features(tasks)

        store(samples, os.path.join(self.out_dir, "%d.pickle" % task_idx))

    def __enable_file_logging(self, idx):
        log_dir = os.path.join(FLAGS.out_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)

        sys.stdout = open(os.path.join(log_dir, "%d.stdout" % idx), "a")
        sys.stderr = open(os.path.join(log_dir, "%d.stderr" % idx), "a")

    def extract_features(self, tasks):
        invocations_by_dataset = {}
        for ds, invocation in tasks:
            if ds not in invocations_by_dataset:
                invocations_by_dataset[ds] = []
            invocations_by_dataset[ds].append(invocation)

        loop_infos_flat = []
        for ds, invocations in invocations_by_dataset.items():
            clang_driver = ClangDriver(
                ds.programming_language,
                ClangDriver.OptimizationLevel.O3,
                [(x, ClangDriver.IncludeDirType.User) for x in ds.additional_include_dirs],
                ds.compiler_flags
            )
            builder = ASTCodeBuilder(clang_driver)
            sample = ds.preprocess(builder, ASTCodeVisitor)

            # Print
            for loop_info in sorted(builder.loop_infos, key=lambda s: s['meta']['num_tokens']):
                print('-' * 80)
                print(loop_info['meta'])
                print()
                print(loop_info['src'])

            loop_infos_flat += [flatten_dict(x) for x in builder.loop_infos]

        return loop_infos_flat


class ReduceTask(MultiProcessedTask):
    def __init__(self, base_dir, num_processes, num_tasks, previous_task, verbose=False):
        super().__init__(base_dir, num_processes, num_tasks, previous_task, verbose)

    def _load_tasks(self):
        filenames_all = get_files(self.in_dir, suffix='.pickle')

        return filenames_all

    def _process_tasks(self, indexed_tasks: list):
        filenames = get_files(self.in_dir, suffix='.pickle')
        bucket = self.__filenames_to_bucket(filenames)

        store(bucket, os.path.join(self.out_dir, "all.pickle"))
        self._store_in_sqlite(bucket)

    def __filenames_to_bucket(self, filenames):
        bucket_full = []
        for filename in filenames:
            with open(filename, 'rb') as f:
                try:
                    bucket_part = pickle.load(f)
                except (TypeError, EOFError, pickle.UnpicklingError) as e:
                    print(e)
                    continue

                if type(bucket_part) is list:
                    bucket_full += bucket_part
                else:
                    bucket_full += [bucket_part]
        return bucket_full

    def _store_in_sqlite(self, loop_infos_flat):
        # Store in SQL DB
        all_keys = set(itertools.chain.from_iterable([x.keys() for x in loop_infos_flat]))
        int_keys = {x for x in all_keys if x.startswith('meta')}

        filename = os.path.join(self.out_dir, 'loops.db')
        is_new_table = not os.path.isfile(filename)

        conn = sqlite3.connect(filename)
        c = conn.cursor()

        if is_new_table:
            int_cols = ', '.join([x + ' INT' for x in int_keys])
            cmd = 'CREATE TABLE IF NOT EXISTS loops(src TEXT, body TEXT, filename TEXT, dataset_name TEXT, ' + int_cols + ')'
            print(cmd)
            c.execute(cmd)
        else:
            existing_cols = [col[1] for col in c.execute('pragma table_info(loops)').fetchall()]
            new_cols = list(set(int_keys) - set(existing_cols))
            for int_col in [x + ' INT' for x in new_cols]:
                cmd = 'ALTER TABLE loops ADD COLUMN ' + int_col + ';'
                print(cmd)
                c.execute(cmd)

        for loop_info in loop_infos_flat:
            columns = ', '.join(loop_info.keys())
            placeholders = ', '.join('?' * len(loop_info))
            sql = 'INSERT INTO loops ({}) VALUES ({})'.format(columns, placeholders)
            c.execute(sql, list(loop_info.values()))

        conn.commit()


def run_tasks(tasks):
    print('All tasks')
    for i, task in enumerate(tasks):
        print(i, task)
        print()

    for task in tasks:
        print('Running task', task)
        task.run()


def main(argv):
    os.makedirs(FLAGS.out_dir, exist_ok=True)
    num_cpus = multiprocessing.cpu_count()

    # Define tasks
    t1 = ExtractTask(
        base_dir=FLAGS.out_dir,
        num_processes=num_cpus,
        num_tasks=10)
    t2 = ReduceTask(
        base_dir=FLAGS.out_dir,
        num_processes=num_cpus,
        num_tasks=1,
        previous_task=t1)

    tasks = [t1, t2]

    # Run tasks
    run_tasks(tasks)


if __name__ == "__main__":
    app.run(main)