import numpy as np
import pandas as pd
from torch.utils.data import Dataset
import torch
import constants as const


class ThreeTankImgDataSet(Dataset):
    """Write me!"""

    def __init__(self, debug=False):
        path = const.X_SPACE_DATA_PATH_DEBUGGING if debug else const.X_SPACE_DATA_PATH
        self.df = pd.read_parquet(path)
        self.x = torch.from_numpy(self.df[const.X_COL_NAMES].values.astype(np.float32))
        self.xdot = torch.from_numpy(self.df[const.XDOT_COL_NAMES].values.astype(np.float32))


    def __len__(self):
        """Size of dataset
        """
        return self.x.shape[0] 

    def __getitem__(self, index):
        """Get one sample"""
        return self.x[index, :], self.xdot[index, :], index 

class ThreeTankBaseDataSet(Dataset):
    """Write me!"""

    def __init__(self, debug=False):
        path = const.Z_SPACE_DATA_PATH 
        self.df = pd.read_parquet(path)
        # scaler = StandardScaler()
        # self.df[const.Z_COL_NAMES + const.Z_DOT_COL_NAMES] = \
            # scaler.fit_transform(self.df[const.Z_COL_NAMES + const.Z_DOT_COL_NAMES])
        self.x = torch.from_numpy(self.df[const.Z_COL_NAMES].values.astype(np.float32))
        self.xdot = torch.from_numpy(self.df[const.Z_DOT_COL_NAMES].values.astype(np.float32))


    def __len__(self):
        """Size of dataset
        """
        return self.x.shape[0] 

    def __getitem__(self, index):
        """Get one sample"""
        return self.x[index, :], self.xdot[index, :], index 

if __name__ == '__main__':
    breakpoint()
    # test for lets have a look
    dataset = ThreeTankBaseDataSet()
    idx = 10
    x, xdot, idx = dataset[idx]
    treakpoint()
