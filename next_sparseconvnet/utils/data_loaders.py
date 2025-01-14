import tables as tb
import numpy  as np
import torch

from enum import auto

from invisible_cities.io   .dst_io  import load_dst
from invisible_cities.types.ic_types import AutoNameEnumBase

from . data_io import get_3d_input


class LabelType(AutoNameEnumBase):
    Classification = auto()
    Segmentation   = auto()


class DataGen_classification(torch.utils.data.Dataset):
    def __init__(self, labels, binsX, binsY, binsZ):
        self.binsX  = binsX
        self.binsY  = binsY
        self.binsZ  = binsZ
        self.labels = labels

    def __getitem__(self, idx):
        filename = self.labels.iloc[idx].filename
        event    = self.labels.iloc[idx].event
        label    = self.labels.iloc[idx].label
        x, y, z, ener = get_3d_input(filename, event, self.binsX, self.binsY, self.binsZ)
        return x, y, z, ener, [label], event #tener eventid puede ser util



class DataGen(torch.utils.data.Dataset):
    def __init__(self, filename, label_type):
        """ This class yields events from pregenerated MC file.
        Parameters:
            filename : str; filename to read
            table_name : str; name of the table to read
                         currently available BinClassHits and SegClassHits
        """
        self.filename   = filename
        if not isinstance(label_type, LabelType):
            raise ValueError(f'{label_type} not recognized!')
        self.label_type = label_type
        self.events     = load_dst(filename, 'DATASET', 'EventsInfo')
        self.bininfo    = load_dst(filename, 'DATASET', 'BinsInfo')

    def __enter__(self):
        self.h5in = tb.open_file(self.filename, 'r')
        return self.h5in

    def __exit__(self, type, value, traceback):
        self.h5in.close()

    def __getitem__(self, idx):
        idx_ = self.events.iloc[idx].dataset_id
        hits  = self.h5in.root.DATASET.Voxels.read_where('dataset_id==idx_')
        if self.label_type == LabelType.Classification:
            label = np.unique(hits['binclass'])
        elif self.label_type == LabelType.Segmentation:
            label = hits['segclass']
        return hits['xbin'], hits['ybin'], hits['zbin'], hits['energy'], label, idx_


def collatefn(batch):
    coords = []
    energs = []
    labels = []
    events = torch.zeros(len(batch)).int()
    for bid, data in enumerate(batch):
        x, y, z, E, lab, event = data
        batchid = np.ones_like(x)*bid
        coords.append(np.concatenate([x[:, None], y[:, None], z[:, None], batchid[:, None]], axis=1))
        energs.append(E)
        labels.append(lab)
        print(lab, E)
        events[bid] = event

    coords = torch.tensor(np.concatenate(coords, axis=0), dtype = torch.long)
    energs = torch.tensor(np.concatenate(energs, axis=0), dtype = torch.float)
    labels = torch.tensor(np.concatenate(labels, axis=0), dtype = torch.int).unsqueeze(-1)

    return  coords, energs, labels, events
