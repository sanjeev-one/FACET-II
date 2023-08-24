import datetime
import os
import shutil
import yaml

# Import MATLAB engine
import matlab.engine

from xopt import Xopt
from pmd_beamphysics import ParticleGroup
from pmd_beamphysics.interfaces.lucretia import lucretia_to_data

# Initialize
counter = 0

# Create unique directory based on current date and time
def create_unique_directory():
    now = datetime.datetime.now()
    dir_name = f"simulation_{now.strftime('%Y-%m-%d_%H-%M-%S')}"
    os.makedirs(dir_name, exist_ok=True)
    return dir_name

directory = create_unique_directory()

def save_beam_to_h5():
    '''assumes that your matlab saves a lucretia.mat file at the end of each simulation. This function converts that file to a .h5 file and saves it in the directory created above. If using this with a different matlab function then this must be updated.'''
    global counter
    # Convert .mat beam file to .h5 format
    P = ParticleGroup(data=lucretia_to_data('lucretia.mat', verbose=True))
    P.write(f'{directory}/lucretia_step_{counter}.h5')
    shutil.copy('lucretia.mat', f'{directory}/lucretia_{counter}.mat')
    counter += 1
    return P

def run_matlab(input_var, quadvalues):
    # Start MATLAB engine
    eng = matlab.engine.start_matlab()
    
    # Assuming the MATLAB function is named 'run' and returns a dict
    '''
    Example of matlab function returning a dict:
    function result = my_function(a, b, c)
    % Some operations
    val1 = a + b;
    val2 = a * c;

    % Return results as a struct
    result = struct('sum', val1, 'product', val2);
    end
    '''
    results = eng.run(input_var[0], input_var[1], input_var[2], quadvalues, input_var[3])
    #uses save_beam_to_h5 definition
    P = save_beam_to_h5()

    # Convert MATLAB dict to python dict
    results = {key: results[key][0] for key in results}

    eng.quit()  # Close MATLAB engine

    return results, P

def evaluate(variables):
    # Extract variables
    input_vars = [variables[key] for key in ["sol_var", "gun_phase", "laser_pulse_length", "bunch_charge"]]
    quadvalues = [variables[key] for key in variables if "QUAD" in key]
    
    results, P = run_matlab(input_vars, quadvalues)
    
    stats_dict = P.twiss('xy', fraction=.95)
    bunch_charge_final = P['charge']
    num_particles = len(P['x'])
    bunch_length = P['sigma_t'] * 1e12  # Converts to ps as there was a rounding error when saving super small values to yaml
    
    dictionary_outputs = {
        "emit_mean": results['emit_mean'],
        "energy": results['energy'],
        "sigx": results['sigx'],
        "sigy": results['sigy'],
        "bunch_length": bunch_length,
        "bunch_charge_final": bunch_charge_final,
        "num_particles": num_particles
    }
    dictionary_outputs.update(stats_dict)
    return dictionary_outputs

# Configuration for optimization see Xopt docs for more info
YAML = f"""
xopt: 
    dump_file: {directory}/dump.yaml
    max_evaluations: 240
generator:
  name: cnsga
  population_size: 80
  output_path: {directory}
  population_file: /data/home/sanjeev/GPT/simulation_2023-08-16_11-18-18/cnsga_population_2023-08-16T16:16:43.690479-07:00.csv
  
  

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
print(X)
X.run()
