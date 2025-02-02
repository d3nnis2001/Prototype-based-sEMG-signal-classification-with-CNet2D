from model.utils import preprocess, to_tensors, list_files
import pandas as pd
import torch
from sklearn.model_selection import train_test_split
from scipy.io import loadmat
from scipy import signal
import os 
from sklearn.utils import shuffle
from model.nina_helper import *

class NearlabDatasetLoader:
    """
    NearlabDatasetLoader class to load Nearlab dataset.

    Parameters:
    ----------
    train_paths : list
        List of file paths for training data.
    test_paths : list
        List of file paths for testing data.

    """
    def __init__(self, train_paths, test_paths):
        self.train_paths = train_paths
        self.test_paths = test_paths

    def load_data(self, split_method="file_split"):
        if split_method == "file_split":
            return self.split_by_file()
        elif split_method == "repetition_wise":
            return self.split_data_by_repetitions()
        elif split_method == "few-shot-learning":
            return self.split_few_shot_learning()
        else:
            raise ValueError("Split does not exist")

    def _read_in_file(self, filepath):
        data = pd.read_csv(filepath, header=None, skiprows=[0])
        X = data.iloc[:, :5120].values
        y = data.iloc[:, 5120].values
        repetitions = data.iloc[:, 5121].values
        y = y - 1
        X = preprocess(X)
        X, y = shuffle(X, y, random_state=39)
        
        return X, y, repetitions

    def _read_in_combo_file(self, filepath):
        data = pd.read_csv(filepath, header=None, skiprows=[0])
        X = data.iloc[:, :5120].values
        y = data.iloc[:, 5120].values
        y2 = data.iloc[:, 5121].values
        repetitions = data.iloc[:, 5122].values
        start = 9
        for i in range(6, 9):
            for j in range(3, 5):
                y = np.where((y == i) & (y2 == j), start, y)
                start += 1
        
        X = preprocess(X)
        X, y = shuffle(X, y, random_state=39)
        
        return X, y, repetitions
    
    def split_by_file(self):
        """
        Splits by rotation. We use 2 rotations for training and one for testing. Ensures generalization across all rotations
        """
        X_train_list, y_train_list = [], []
        X_test_list, y_test_list = [], []

        for train_file in self.train_paths:
            X_train, y_train, _ = self._read_in_file(train_file)
            X_train_list.append(X_train)
            y_train_list.append(y_train)
        
        for test_file in self.test_paths:
            X_test, y_test, _ = self._read_in_file(test_file)
            X_test_list.append(X_test)
            y_test_list.append(y_test)
        
        # Combine the data
        X_train = np.concatenate(X_train_list, axis=0)
        y_train = np.concatenate(y_train_list, axis=0)
        X_test = np.concatenate(X_test_list, axis=0)
        y_test = np.concatenate(y_test_list, axis=0)

        X_train, X_val, y_train, y_val = train_test_split(X_train, y_train, test_size=0.2, random_state=39, shuffle=True)
        
        # Convert into pytorch tensors for the model
        X_train, y_train = to_tensors(X_train, y_train)
        X_val, y_val = to_tensors(X_val, y_val)
        X_test, y_test = to_tensors(X_test, y_test)
        return X_train, y_train, X_val, y_val, X_test, y_test

    def split_data_by_repetitions(self):
        """
        Splits the data by taking 3/5 of repetitions for training and 2/5 for testing
        for each movement in each hand orientation
        """
        X_train_list, y_train_list = [], []
        X_test_list, y_test_list = [], []
        
        # Process all files
        for filepath in self.train_paths + self.test_paths:
            X, y, repetitions = self._read_in_file(filepath)
            
            # For each movement class
            for movement in np.unique(y):
                # Get all indices for the current movement
                movement_indices = np.where(y == movement)[0]
                # Get all repetitions for the current movement
                movement_repetitions = repetitions[movement_indices]
                
                # Get all unique repetitions
                unique_reps = np.unique(movement_repetitions)
                # Number of repetitions
                num_reps = len(unique_reps)
                # Take 3/5 of repetitions for training
                num_train_reps = int(np.ceil(3 * num_reps / 5))
                
                # Randomly select repetition numbers for training
                train_rep_nums = np.random.choice(unique_reps, size=num_train_reps, replace=False)
                
                # Split data based on the selected repetition numbers
                train_indices = movement_indices[np.isin(movement_repetitions, train_rep_nums)]
                test_indices = movement_indices[~np.isin(movement_repetitions, train_rep_nums)]
                
                X_train_list.append(X[train_indices])
                y_train_list.append(y[train_indices])
                X_test_list.append(X[test_indices])
                y_test_list.append(y[test_indices])
        
        # Combine all data
        X_train = np.concatenate(X_train_list, axis=0)
        y_train = np.concatenate(y_train_list, axis=0)
        X_test = np.concatenate(X_test_list, axis=0)
        y_test = np.concatenate(y_test_list, axis=0)

        X_train, X_val, y_train, y_val = train_test_split(X_train, y_train, test_size=0.2, random_state=39, shuffle=True)
        
        X_train, y_train = to_tensors(X_train, y_train)
        X_test, y_test = to_tensors(X_test, y_test)
        X_val, y_val = to_tensors(X_val, y_val)
        
        return X_train, y_train, X_val, y_val, X_test, y_test
    
    def split_few_shot_learning(self):
        """
        Split of basic and combo movement for FSL
        """
        X_train_list, y_train_list = [], []
        X_test_list, y_test_list = [], []

        for train_file in self.train_paths:
            X_train, y_train, _ = self._read_in_file(train_file)
            X_train_list.append(X_train)
            y_train_list.append(y_train)
        
        for test_file in self.test_paths:
            X_test, y_test, _ = self._read_in_combo_file(test_file)
            X_test_list.append(X_test)
            y_test_list.append(y_test)

        X_train = np.concatenate(X_train_list, axis=0)
        y_train = np.concatenate(y_train_list, axis=0)
        X_test = np.concatenate(X_test_list, axis=0)
        y_test = np.concatenate(y_test_list, axis=0)

        X_train, X_val, y_train, y_val = train_test_split(X_train, y_train, test_size=0.2, random_state=39, shuffle=True)
        
        # Convert into pytorch tensors for the model
        X_train, y_train = to_tensors(X_train, y_train)
        X_val, y_val = to_tensors(X_val, y_val)
        X_test, y_test = to_tensors(X_test, y_test)
        return X_train, y_train, X_val, y_val, X_test, y_test


        


class NinaProDatasetLoader:
    """
    NinaProDatasetLoader class to load and preprocess NinaPro dataset.
    
    Parameters:
    ----------
    folder_path : str
        Path to the folder containing NinaPro database files
    subject : int
        Subject number to load (1-27 for DB1, 1-40 for DB2)
    database : int
        Which NinaPro database to use (1 or 2)
    window_length : int
        Length of the sliding window in samples
    window_increment : int
        Increment between consecutive windows in samples
    rest_length_cap : int, optional
        Number of seconds of rest data to keep before/after movement (default: 5)
    """
    def __init__(self, folder_path, subject, database, window_length=512, window_increment=128, rest_length_cap = 5):
        
        self.folder_path = folder_path
        self.subject = subject
        self.database = database
        self.window_length = window_length
        self.window_increment = window_increment
        self.rest_length_cap = rest_length_cap
        
    def load_data(self, split_method = "repetition_wise", test_reps = 2):
        """
        Load and preprocess the NinaPro dataset.
        
        Parameters:
        ----------
        split_method : str
            Method to split the data ("repetition_wise" or "balanced")
        test_reps : int
            Number of repetitions to use for testing
        
        """
        info = db2_info()
        reps = info["rep_labels"]
        # Load in Ninapro data based on database
        if self.database == 1:
            data = import_db1(self.folder_path, self.subject, self.rest_length_cap)
        elif self.database == 2:
            data = import_db2(self.folder_path, self.subject, self.rest_length_cap)
        else:
            raise ValueError("Database must be 1 or 2")
        
        # Remove the resting movement
        mask = data["move"] != 0
        data["emg"] = data["emg"][mask]
        data["move"] = data["move"][mask]
        data["rep"] = data["rep"][mask]
            
        # Split into train test set
        if split_method == "repetition_wise":
            train_reps, test_reps = gen_split_rand(reps, test_reps, 12, base=[2, 5])
        elif split_method == "balanced":
            train_reps, test_reps = gen_split_balanced(reps, test_reps, base=[2, 5])
        else:
            raise ValueError("Split does not exist")
            
            
        # Use first split if multiple were generated
        train_reps = train_reps[0]
        test_reps = test_reps[0]
        # Normalize data
        normalized_emg = normalise_emg(data["emg"], data["rep"], train_reps)

        # Convert to Dataframe for the filter function
        emg_df = pd.DataFrame(normalized_emg, columns=[f"channel_{i+1}" for i in range(normalized_emg.shape[1])])
        emg_df["stimulus"] = data["move"]
        emg_df["repetition"] = data["rep"]

        filtered_emg = self.filter_data(emg_df, f=(10, 450), butterworth_order=4, btype="bandpass")
        emg_filtered = filtered_emg.values[:, :12]
        # Get windowed data for training set
        X_train, y_train, _ = get_windows(
            train_reps,
            self.window_length,
            self.window_increment,
            emg_filtered,
            data["move"],
            data["rep"]
        )

        train_mask = y_train > 0
        X_train = X_train[train_mask]
        y_train = y_train[train_mask]
        y_train -= 1
        
        # Get windowed data for test set
        X_test, y_test, _ = get_windows(
            test_reps,
            self.window_length,
            self.window_increment,
            emg_filtered,
            data["move"],
            data["rep"]
        )

        test_mask = y_test > 0
        X_test = X_test[test_mask]
        y_test = y_test[test_mask]
        y_test -= 1
        # Shuffle the data
        X_train, y_train = shuffle(X_train, y_train, random_state=39)
        X_test, y_test = shuffle(X_test, y_test, random_state=39)

        X_train, X_val, y_train, y_val = train_test_split(
            X_train, y_train, test_size=0.2, random_state=42, stratify=y_train
        )
        
        # Convert to PyTorch tensors
        X_train = torch.FloatTensor(X_train).squeeze(-1)
        y_train = torch.LongTensor(y_train)
        X_test = torch.FloatTensor(X_test).squeeze(-1)
        y_test = torch.LongTensor(y_test)
        X_val = torch.FloatTensor(X_val).squeeze(-1)
        y_val = torch.LongTensor(y_val)
        # Permutate the data to (n_samples, n_channels, n_timepoints)
        X_train = X_train.permute(0, 2, 1)
        X_test = X_test.permute(0, 2, 1)
        X_val = X_val.permute(0, 2, 1)

        
        return X_train, y_train, X_val, y_val, X_test, y_test
        
    
    def load_few_shot_learning_data(self):
        """
        Load and preprocess the NinaPro dataset for few-shot learning.
        It takes Exercise B and C as training data and Exercise D as testing data.
        """

        info = db2_info()
        reps = info["rep_labels"]

        if self.database == 1:
            data = import_db1(self.folder_path, self.subject, self.rest_length_cap)
        elif self.database == 2:
            data = import_db2(self.folder_path, self.subject, self.rest_length_cap)
        else:
            raise ValueError("Database must be 1 or 2")
        
        # Remove the resting movement
        mask = data["move"] != 0
        data["emg"] = data["emg"][mask]
        data["move"] = data["move"][mask]
        data["rep"] = data["rep"][mask]
        
        # Normalize data
        normalized_emg = normalise_emg(data["emg"], data["rep"], reps)
        # Convert to Dataframe for the filter function
        emg_df = pd.DataFrame(normalized_emg, columns=[f"channel_{i+1}" for i in range(normalized_emg.shape[1])])

        emg_df["stimulus"] = data["move"]
        emg_df["repetition"] = data["rep"]

        filtered_emg = self.filter_data(emg_df, f=(10, 450), butterworth_order=4, btype="bandpass")
        emg_filtered = filtered_emg.values[:, :12]
        
        # Get all windows
        X_all, y_all, _ = get_windows(
            np.unique(data["rep"]),
            self.window_length,
            self.window_increment,
            emg_filtered,
            data["move"],
            data["rep"]
        )
        
        # Split by class for FSL (0 is excluded as it is the rest movement and influences the overall performance significantly)
        mask_train = (y_all > 0) & (y_all < 41)
        mask_test = (y_all >= 41) & (y_all < 50)
        X_train, y_train = X_all[mask_train], y_all[mask_train]
        X_test, y_test = X_all[mask_test], y_all[mask_test]
        
        # Shuffle the data
        X_train, y_train = shuffle(X_train, y_train, random_state=39)
        X_test, y_test = shuffle(X_test, y_test, random_state=39)

        X_train, X_val, y_train, y_val = train_test_split(
            X_train, y_train, test_size=0.2, random_state=42, stratify=y_train
        )

        y_train -= 1
        y_test -= 1
        y_val -= 1
        
        # Convert to PyTorch tensors
        X_train = torch.FloatTensor(X_train).squeeze(-1)
        y_train = torch.LongTensor(y_train)
        X_test = torch.FloatTensor(X_test).squeeze(-1)
        y_test = torch.LongTensor(y_test)
        X_val = torch.FloatTensor(X_val).squeeze(-1)
        y_val = torch.LongTensor(y_val)

        # Permutate the data into the correct shape
        X_train = X_train.permute(0, 2, 1)
        X_test = X_test.permute(0, 2, 1)
        X_val = X_val.permute(0, 2, 1)
        return X_train, y_train, X_val, y_val, X_test, y_test

    
    # from https://github.com/parasgulati8/NinaPro-Helper-Library/blob/master/NinaPro_Utility.py
    def filter_data(self, data, f, butterworth_order = 4, btype = "lowpass"):
        emg_data = data.values[:,:12]
        
        f_sampling = 2000
        nyquist = f_sampling/2
        if isinstance(f, int):
            fc = f/nyquist
        else:
            fc = list(f)
            for i in range(len(f)):
                fc[i] = fc[i]/nyquist
                
        b,a = signal.butter(butterworth_order, fc, btype=btype)
        transpose = emg_data.T.copy()
        
        for i in range(len(transpose)):
            transpose[i] = (signal.lfilter(b, a, transpose[i]))
        
        filtered = pd.DataFrame(transpose.T)
        filtered["stimulus"] = data["stimulus"]
        filtered["repetition"] = data["repetition"]
        
        return filtered