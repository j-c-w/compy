import os.path

import sqlite3

from compy.datasets import GeneralDataset
from compy.representations.extractors.extractors import Visitor
from compy.representations.ast_graphs import ASTCodeBuilder
from compy.representations.ast_graphs import ASTCodeVisitor
from compy.representations.extractors import ClangDriver
from compy.utils import flatten_dict



datasets = [
  # LivermorecDataset(),
  # GeneralDataset('https://github.com/libav/libav.git', 'libav'),
  # GeneralDataset('https://github.com/mirror/x264.git', 'x264'),
  # GeneralDataset('https://github.com/ImageMagick/ImageMagick.git', 'ImageMagick'),
  # GeneralDataset('https://github.com/WinMerge/freeimage.git', 'freeimage'),
  GeneralDataset('https://github.com/DentonW/DevIL.git', 'DevIL', 'DevIL'),
  GeneralDataset('https://github.com/FFmpeg/FFmpeg.git', 'ffmpeg'),
  # GeneralDataset('https://github.com/opencv/opencv.git', 'opencv'),
]

loop_infos_flat = []

for ds in datasets:
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


    # Store in SQL DB
    all_keys = set(itertools.chain.from_iterable([x.keys() for x in loop_infos_flat]))
    int_keys = {x for x in all_keys if x.startswith('meta')}

    filename = 'loops.db'
    is_new_table = not os.path.isfile(filename)

    conn = sqlite3.connect(filename)
    c = conn.cursor()


    if is_new_table:
        int_cols = ', '.join([x + ' INT' for x in int_keys])
        cmd = 'CREATE TABLE IF NOT EXISTS loops(src TEXT, body TEXT, ' + int_cols + ')'
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

print('done')