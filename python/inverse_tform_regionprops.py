from collections import defaultdict
import os
import re
import h5py
import itk
import tifffile
from skimage import io
from skimage.measure import regionprops
import numpy as np
import pandas as pd
import argparse
from pathlib import Path

def parse_args():
    parser = argparse.ArgumentParser(description='Allen-to-Experiment Transform and Regionprops Calculation')
    parser.add_argument('basedir', type=Path, help='path to base directory containing the experiment')
    parser.add_argument('animal', type=str, help='animal folder name')
    args = parser.parse_args()

    return args

def read_h5_image(file_path, dataset_name, th=100):
    with h5py.File(file_path, 'r') as h5_file:
        # Replace 'dataset_name' with the actual dataset name in your .h5 file
        data = h5_file[dataset_name][:]
        data[data<100] = 100
        return itk.image_view_from_array(data)

def match_h5_files_by_channels(base_dir):
    file_groups = defaultdict(lambda: {"ch0": None, "ch1": None, "ch2": None})
    
    # Walk through all directories and files in base_dir
    for dirpath, dirnames, filenames in os.walk(base_dir):
        for filename in filenames:
            if filename.endswith('.h5'):
                # Extract the directory name
                dir_name = os.path.basename(dirpath)
                full_path = os.path.join(dirpath, filename)
                
                # Match channel files and exclude "main" files
                if "uni_tp-0_ch-0" in filename:
                    file_groups[dir_name]["ch0"] = full_path
                elif "uni_tp-0_ch-1" in filename:
                    file_groups[dir_name]["ch1"] = full_path
                elif "uni_tp-0_ch-2" in filename:
                    file_groups[dir_name]["ch2"] = full_path
    
    # Filter out groups that don't have all 3 channels (ch0, ch1, ch2)
    valid_file_sets = {key: value for key, value in file_groups.items() if all(value.values())}
    
    return valid_file_sets

def do_the_transform(base_dir,animal):
    animals = match_h5_files_by_channels(base_dir)
    current = animals[animal]

    print('Loading the atlas....')
    mv = itk.imread(f'/nrs/spruston/Boaz/I2/atlas10_hemi.tif',pixel_type=itk.US)
    fx = read_h5_image(current['ch0'], 'Data')

    print('Loading the parameter files....')
    param_dir = f'/nrs/spruston/Boaz/I2/itk_new/'
    parameter_object = itk.ParameterObject.New()
    rigid_parameter_map = parameter_object.GetDefaultParameterMap('rigid', 8)
    rigid_parameter_map['HowToCombineTransforms'] = ['Compose']
    parameter_object.AddParameterMap(rigid_parameter_map)
    parameter_object.AddParameterFile(param_dir+f'Order1_Par0000affine.txt')
    parameter_object.AddParameterFile(param_dir+f'Order3_Par0000bspline.txt')
    parameter_object.AddParameterFile(param_dir+f'Order4_Par0000bspline.txt')
    parameter_object.AddParameterFile(param_dir+f'Order5_Par0000bspline.txt')


    print('Calculating the inverse....')

    output_dir= os.path.join(base_dir, animal, 'invert_test')
    if not os.path.isdir(output_dir):
        os.mkdir(output_dir)

    inverse_transform_parameters = itk.elastix_registration_method(fx, mv,
                                            parameter_object=parameter_object,
                                            log_to_file=True,
                                            output_directory = output_dir,
                                            initial_transform_parameter_file_name=os.path.join(f'/nrs/spruston/Boaz/I2/itk_new',"TForm_Invert_Init.txt"))

    transformix_object = itk.TransformixFilter.New()
    transformix_object.SetTransformParameterObject(inverse_transform_parameters[1])

    writeParam = transformix_object.GetTransformParameterObject()

    for index in range(writeParam.GetNumberOfParameterMaps()):
        parameter_map_test = writeParam.GetParameterMap(index)
        parameter_object.WriteParameterFile(parameter_map_test,output_dir+"/TestInverse_Parameters.{0}.txt".format(index))
        
        
def calculate_region_props_from_inverse(base_dir, animal):

    animals = match_h5_files_by_channels(base_dir)
    print(animals)
    current = animals[animal]

    print('Reading multi-channel image...')
    image_list = []

    for name, path in current.items():
        print(f'Reading {path}')
        image_list.append(read_h5_image(path, 'Data'))
    multichannel_image = np.stack(image_list, axis=-1)

    print('Reading annotation file...')
    annotation_np_swapped = tifffile.imread(os.path.join(f'/nrs/spruston/Boaz/I2/old','annotatin10_hemi.tif'))
    annotation = itk.GetImageFromArray(annotation_np_swapped.astype(np.uint16))

    # print('Reading parameter files...')
    output_dir = os.path.join(base_dir,animal,"invert_test")

    parameter_files = [output_dir + "/TransformParameters.{0}.txt".format(i) for i in range(5)]
    parameter_object = itk.ParameterObject.New()
    parameter_object.AddParameterFile(os.path.join(f'/nrs/spruston/Boaz/I2/itk_new',"TForm_Invert_Init.txt"))

    ### For this specific animal 
    # parameter_object.AddParameterFile(os.path.join(ddir,"TForm_Invert_Init_ANM549057.txt"))
    for p in parameter_files:
        parameter_object.AddParameterFile(p)

    parameter_object.SetParameter(0,"InitialTransformParameterFileName", "NoInitialTransform")
    parameter_object.SetParameter(1,"InitialTransformParameterFileName", "NoInitialTransform")

    for index in range(parameter_object.GetNumberOfParameterMaps()):
        print(index)
        parameter_object.SetParameter(index,"FinalBSplineInterpolationOrder","0")

    print('Transforming annotation image...')
    transformix_filter = itk.TransformixFilter.New(Input=annotation, TransformParameterObject=parameter_object)
    transformix_filter.SetComputeSpatialJacobian(False)
    transformix_filter.SetComputeDeterminantOfSpatialJacobian(False)
    transformix_filter.SetComputeDeformationField(False)
    transformix_filter.Update()

    # Get the transformed image
    transformed_image = transformix_filter.GetOutput()
    print('Writing the transformed annotation image...')
    output_image_path = os.path.join(output_dir,'transformed_annotation_10.tif')

    itk.imwrite(transformed_image, output_image_path)

    print('Calculating region props...')

    regions = regionprops(transformed_image,intensity_image=multichannel_image)

    non_empty_regions = [region for region in regions if region.area > 0]

    props = [{'label' : region.label, 'intensity_mean' : region.intensity_mean, 'area' : region.area} for region in non_empty_regions]
    print('finished region props')

    df_stats = pd.DataFrame.from_dict(props)
    df_stats.rename(columns={
        'intensity_mean-0': 'Mean_ch0',
        'intensity_mean-1': 'Mean_ch1',
        'intensity_mean-2': 'Mean_ch2',
        'area': 'N',  # N represents the area (number of pixels in the region)
        'label': 'Region'
    }, inplace=True)

    csv_path = os.path.join(output_dir,'region_stats.csv')
    print(f'saving csv to {csv_path}')
    df_stats.to_csv(csv_path, index=False)


def main():
    
    args = parse_args()
    
    do_the_transform(base_dir = args.basedir, animal = args.animal)
    calculate_region_props_from_inverse(base_dir = args.basedir, animal = args.animal)
    
if __name__ == '__main__':
    
    main()
