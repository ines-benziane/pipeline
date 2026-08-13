import pathlib
import PIL
import pandas as pd
import numpy as np
from mutools import io
from mutools.tables import getresults

import logging
logging.basicConfig(level=logging.INFO)

# local
from mutools.utils import msquares

#
# user defined
WORK = pathlib.Path('/mnt/rmn_files/Users/IB/donnees_test/config/work')
DEST = pathlib.Path('results')

# configuration file
CONFIG = pathlib.Path('config') / 'results_config.yml'

# examinations
INDICES = ['vol.2', 'vol.3', 'vol.4']

# methods
METHODS = ['dixon3pt_t2slice', 'dixon3pt_t2slice_legs']

#
# other constants
INFO_SUFFIXES = ['.yml']
VOL_SUFFIXES = ['.mha', '.mhd', 'nii', '.nii.gz']

#
# load config
print('load config')
config_all = io.config.read(CONFIG)

for METHOD in METHODS:
    if METHOD not in config_all:
        print(f'Unknown method: {METHOD}')
        continue
    config = config_all[METHOD]
    print(f'\n====== METHOD: {METHOD} ======')

    for INDEX in INDICES:
        print(f'\n=== {INDEX} ===')

        # load data
        print('load data')
        inputs = config['inputs']
        info, volumes = {}, {}
        for input in (inputs if isinstance(inputs, list) else [inputs]) if inputs is not None else []:
            datadir = WORK / INDEX / input
            for file in datadir.glob('*'):
                for suffix in VOL_SUFFIXES:
                    if file.name.endswith(suffix):
                        name = file.name[:-len(suffix)]
                        volumes[name] = io.read(file)
                        continue
                for suffix in INFO_SUFFIXES:
                    if file.name.endswith(suffix):
                        name = file.name[:-len(suffix)]
                        info[name] = io.config.read(file)

        # load ROI
        print('load roi')
        roidir = WORK / INDEX / config['roi']
        for suffix in VOL_SUFFIXES:
            file = roidir / f'roi{suffix}'
            if file.is_file():
                roi = io.read(file)
                if roi.sum() == 0:
                    print('warning: empty ROI')
                break
        labels = None
        for file in roidir.glob('labels*.txt'):
            labels = io.read_labels(file)
            break

        # extract results
        print('compute stats')
        tasks = config['variables']
        defaults = config.get('defaults', {})
        reference = config.get('options', {}).get('reference')
        table = getresults.extract(tasks, roi, volumes, labels=labels, defaults=defaults, reference=reference)
        table.reset_index(inplace=True)

        # store table
        print('store table')
        dest = DEST / f'{INDEX}_{METHOD}'
        dest.mkdir(parents=True, exist_ok=True)
        table.to_excel((dest / 'results').with_suffix('.xlsx'), index=False)
        table.to_csv((dest / 'results').with_suffix('.csv'), index=False)
        print(f'Résultats sauvegardés : {dest}')
