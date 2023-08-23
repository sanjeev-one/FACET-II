from xopt import Xopt
import subprocess  # for matlab function
import yaml
from pmd_beamphysics.interfaces.lucretia import lucretia_to_data # to save the beam to h5 files
from pmd_beamphysics import ParticleGroup
counter = 0 # to keep track of how many runs for saving the beam to h5 files
import shutil
import pandas as pd
import numpy as np

import time
import os
import datetime

# Get the current date and time
now = datetime.datetime.now()

# Format it as a string
now_str = now.strftime("%Y-%m-%d_%H-%M-%S")

# Use this string to create a unique directory name
directory = f"simulation_{now_str}"

# Create the directory
os.makedirs(directory, exist_ok=True)

def save_beam_to_h5():
  global counter
  P = ParticleGroup(data=lucretia_to_data('lucretia.mat', verbose=True)) #assumes file is in the same directory as this script and called lucretia.mat
  P.write(f'{directory}/lucretia_step_{counter}.h5')
  shutil.copy('lucretia.mat', f'{directory}/lucretia_{counter}.mat')

  
  counter += 1
  

  
  return P

def run_matlab(input_var,quadvalues):
    start = time.time()
    print(f"start of matlab function {start}")
    print(f" inputvar:  {input_var}")
    print(f" psvalues: {quadvalues}")
    matlab_cmd = (
        f'/home/sanjeev/MATLAB/R2023a/bin/matlab -nodesktop -nosplash -r "run({input_var[0]},{input_var[1]},{input_var[2]},{quadvalues},{input_var[3]}); exit;"'
    )
    print(f" matlab command: {matlab_cmd}      ")
    process = subprocess.Popen(matlab_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    print(f"matlab command just ran and it took {start - time.time()} seconds")
    print(f"Out file: {stdout}")
    print(f"Error file: {stderr}")
    # Wait for the command to finish
    process.wait()
    P = save_beam_to_h5() # converts the .mat beam file to.h5 file
    with open("output.txt", "r") as file:
    # read the content of the file
        content = file.read()

        # split the content on 'Emittance: ', ' Energy: ', 'sigx: ', and 'sigy: '
        parts = content.split("Emittance: ")[1].split(" Energy: ")
        emittance_part, energy_sigx_part = parts[0], parts[1]

        # further split emittance on ' / ' to get emittance_x and emittance_y
        emittance_x, emittance_y = map(float, emittance_part.split(" / "))

        # further split energy_sigx_part on 'sigx: ' to get energy and sigx
        energy, sigx_part = map(str.strip, energy_sigx_part.split("sigx: "))

        # convert energy and sigx to float
        energy = float(energy)
        sigx = float(sigx_part.split()[0])  # assuming sigx is the first part before the whitespace

        # get sigy value
        sigy = float(content.split("sigy: ")[1].strip())  # assuming sigy is the last value in the content

        # now you can use the variables emittance_x, emittance_y, energy, sigx, and sigy
        print(f"Emittance X: {emittance_x}")
        print(f"Emittance Y: {emittance_y}")
        print(f"Energy: {energy}")
        print(f"SigX: {sigx}")
        print(f"SigY: {sigy}")

    return emittance_x, emittance_y, energy, sigx, sigy, P

    


def evaluate(variables):
    x1 = variables["sol_var"] # solenoid variable
    x2 = variables["gun_phase"] # gun phase variable
    x3 = variables["laser_pulse_length"] # laser pulse length
    x4 = variables["bunch_charge"] #initial bunch charge
    
   
    q1 = variables["QUAD:IN10:361:BCTRL"]
    q2 = variables["QUAD:IN10:371:BCTRL"]
    q3 = variables["QUAD:IN10:425:BCTRL"]
    q4 = variables["QUAD:IN10:441:BCTRL"]
    q5 = variables["QUAD:IN10:511:BCTRL"]
    q6 = variables["QUAD:IN10:525:BCTRL"]
    
    quadvalues = [q1, q2, q3, q4, q5, q6]
    print("sending variables to run_matlab")
    # Run the MATLAB simulation
    emittance_x, emittance_y, energy, sigx, sigy, P = run_matlab([x1,x2,x3,x4],quadvalues)
    
    
    stats_dict = P.twiss('xy', fraction=.95)
   
    """ twiss example {'alpha_x': 0.6566386971532087,
 'beta_x': 2.179681313728797,
 'gamma_x': 0.6565979942043649,
 'emit_x': 1.3291022942309809e-08,
 'eta_x': -0.011852427781245511,
 'etap_x': -0.0007844627511422239,
 'norm_emit_x': 3.2507969244663244e-06,
 'alpha_y': 0.06604816927901802,
 'beta_y': 1.7035702570288533,
 'gamma_y': 0.5895632167333026,
 'emit_y': 1.3644803060887649e-08,
 'eta_y': -0.004043344024887415,
 'etap_y': -0.0003820726821121405,
 'norm_emit_y': 3.33734373189341e-06} """
 
    bunch_charge_final = P['charge']
    emittance_x = stats_dict['norm_emit_x']
    emittance_y = stats_dict['norm_emit_y']

  # Constrain number of particles:
    num_particles = len(P['x'])
  
  
  # find bunch length
    bunch_length = P['sigma_t']
    #convert to ps
    bunch_length = bunch_length * 1e12

    emittance_mean = (emittance_x * emittance_y) ** 0.5
    dictionary_outputs = {"emit_mean": emittance_mean, "energy": energy, "sigx": sigx, "sigy": sigy, "bunch_length": bunch_length, "bunch_charge_final": bunch_charge_final, }
    dictionary_outputs["num_particles"] = num_particles
    dictionary_outputs.update(stats_dict)


    return dictionary_outputs




YAML = f"""
xopt: 
    dump_file: {directory}/dump.yaml
    max_evaluations: 240
generator:
  name: cnsga
  population_size: 80
  output_path: {directory}
  population file:  /home/sanjeev/GPT/simulation_2023-08-09_14-26-39/cnsga_population_2023-08-11T00:20:40.600627-07:00.csv
  
  

evaluator:
  function: __main__.evaluate

vocs:
  variables:
    sol_var: [0.1, .3]
    gun_phase: [270, 310]
    bunch_charge: [1.9e-9, 2.1e-9]
    QUAD:IN10:361:BCTRL: [-.3, .3]
    QUAD:IN10:371:BCTRL: [-.3, .3]
    QUAD:IN10:425:BCTRL: [-.3, .3]
    QUAD:IN10:441:BCTRL: [-.3, .3]
    QUAD:IN10:511:BCTRL: [-.3, .3]
    QUAD:IN10:525:BCTRL: [-.3, .3]
  objectives:
    emit_mean: 'MINIMIZE'
    bunch_length: 'MINIMIZE'
  constraints:
    num_particles: [GREATER_THAN, 9000]
  constants: 
    laser_pulse_length: 4.4999e-12

    
"""
config = yaml.safe_load(YAML)

X = Xopt(config=config)


#setup data for the scan





print(X)

X.evaluate_data()

print("Program has finished running")