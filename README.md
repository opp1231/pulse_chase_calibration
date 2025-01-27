# Pulse-Chase Calibration
ITK wrappers for registration of Allen atlas to cleared hemibrains + regional covariance measurements across experiments

#
This directory contains two files: one python script for using itk to calculate the forward (Experiment-to-Allen) and reverse (Allen-to-Experiment) transforms and calculate the resulting region props in both atlas and experiment space; and a jupyter notebook which calculates regional intensity covariances across experiments for raw, global-volume-corrected, and regional-volume-corrected intensities.

## Dependencies
Both the python script and jupyter notebook require the following packages:
+   h5py
+   tifffile
+   scikit-image
+   numpy
+   pandas
These can be installed using your package manager of choice (e.g. pip or a minimal conda such as the miniforge distribution)

## Cluster Usage
The python script for registration was run on the Janelia compute cluster using 16 slots and runs for ~8 hours.

## Allen-to-Experiment (Inverse) Transform
This python script is run by running the executable as follows:
```
    python tform_regionprops.py /path/to/exerpiment/dir/ ANMXXXXXX_JFXXX
```

The experiment path should be the folder which contains all experiments from a given run. The animal name (ANMXXXXXX_JFXXX) correponds to the specific experiment in question. The script will first calculate the regisration(s) of the experimental volume to the 10um Allen atlas using itk (and then the reverse). The parameter files are adapted from those created by the Emily Dennis lab at Janelia. They are largely similar, though the inverse transform includes a first step of an isometric stretch.

Then, using these transform parameters, it calculates region properties of the experimental volume using the mapped Allen annotations. These are saved as a .csv and will be processed/used in the jupyter notebook.

## Regional Covariances
This jupyter notebook can be run cell-by-cell. The first few blocks set filepaths and imports the region properties calculated from the forward (experiment-to-Allen) registration.
The primary function collects all region properties and computes regional intensity covariances for raw, global-volume-corrected and region-volume-corrected intensities. These covariances are then plotted as heatmaps.