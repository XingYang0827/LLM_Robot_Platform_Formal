# Libraries to download
import os
import paramiko
import pyinotify
import time
from transformers import AutoTokenizer, AutoModelForCausalLM

#-----------------------------------LOAD TOKENIZER AND MODEL----------------------------------------
tokenizer = AutoTokenizer.from_pretrained("WizardLM/WizardCoder-15B-V1.0")
model = AutoModelForCausalLM.from_pretrained("WizardLM/WizardCoder-15B-V1.0", device_map='auto')
#model = AutoModelForCausalLM.from_pretrained("WizardLM/WizardCoder-15B-V1.0", device_map='sequential', max_memory={0: '49 GiB'}, revision='main', low_cpu_mem_usage = True, offload_folder='offload')
print("Model Loaded")

# Path to the necessary files
task_file_path = '/home/pragya/LLMCode/instruction.txt' # User Task sent by Jetson
code_file_path = '/home/pragya/LLMCode/LLM_generated_code.py' # Destination of output code created by LLM
api_list = ['/home/pragya/LLMCode/create3api.txt'] # Descriptions of functions for each of the devices on the robot
remote_path = '/home/nesl/desktopTransferredCode.py' # Path to store file in Jetson

# The directory that the EventHandler should monitor for changes
dir_to_watch = os.path.abspath('/home/pragya/LLMCode')
watcher_manager = pyinotify.WatchManager()

#----------------------------- DEFINE THE EVENT HANDLER ---------------
class EventHandler(pyinotify.ProcessEvent):
    '''
    def process_IN_MODIFY(self, event):
        file_path = os.path.join(event.path, event.name)
        if file_path == task_file_path:
            print(f"File: {task_file_path} is being modified...")
    '''
    def process_IN_CLOSE_WRITE(self, event):
        file_path = os.path.join(event.path, event.name)
        if file_path == task_file_path:
            # Process the file update event
            cur_time = time.ctime(time.time())
            print(f"File updated: {file_path} at {cur_time}")
            central_loop(file_path) #run the central_loop function when the file is updated
            
#----------------------------- AUXILIARY FUNCTIONS ------------------

def generate_code():
    '''
    First, it creates the prompt by appending the user given input and the APIs of all the different hardware systems.
    Then it passes it into the LLM to generate an output. Upon receiving the output, it writes only the code portion of the output into a .py file.
    '''
    
    print("Running model.")
    # read from prompt file
    try:
        # first record the user task sent by the Jetson
        with open (task_file_path, 'r') as prompt_file:
            prompt = prompt_file.read()
            
        # append the APIs to the prompt
        for api in api_list:
            with open (api, 'r') as prompt_file:
                prompt += prompt_file.read()
                
    except Exception as e:
        print("Error when read from file prompt.txt:", str(e))
        exit(e)
        
    # start recording how long it takes to produce an output
    start_time = time.time()
    
    # tokenize prompt and generate output using model
    try:
        '''
        Following is how the prompt should be structured for WizardCoder-15B:
            prompt = "Below is an instruction that describes a task. Write a response that appropriately completes the request.\n\n### Instruction:\n{instruction}\n\n### Response: "
        For Vicuna:
            prompt = "A chat between a curious user and an artificial intelligence assistant. The assistant gives helpful, detailed, and polite answers to the user's questions. USER: hello, who are you? ASSISTANT: "
        '''
        
        inputs = tokenizer(prompt, return_tensors="pt").to("cuda").input_ids
        outputs = model.generate(inputs, pad_token_id = tokenizer.pad_token_id, bos_token_id = tokenizer.bos_token_id, eos_token_id = tokenizer.eos_token_id,max_new_tokens = 10000, temperature=0.2, do_sample=True, top_k=15, top_p=0.95)
        #outputs = model.generate(inputs, pad_token_id = tokenizer.pad_token_id, bos_token_id = tokenizer.bos_token_id, eos_token_id = tokenizer.eos_token_id,max_new_tokens = 10000, temperature=0.2, do_sample=False)
    except Exception as e:
        print("Error when tokenize input the generate output:", str(e))
        exit(e)

    # decode output
    try:
        code = tokenizer.batch_decode(outputs, skip_special_tokens=True)
    except Exception as e:
        print("Error when decoding:", str(e))
        exit(e)
        
    # record how long it took to execute the file
    end_time = time.time()
    time_used = end_time - start_time
    print("Finish Generating Code:", time_used)

    # extract the code from the code output
    try:
        with open(code_file_path, 'w', encoding='UTF-8') as code_file:
            for item in code:
                print(item)
                first_index = item.find("```python")
                if first_index == -1:
                    continue
                first_index += len("```python")
                last_index = item[first_index:].find("```") + first_index
                code_file.write(str(item[first_index:last_index]) + '\n')
    except Exception as e:
        print("Error when write file LLM_genereated_code_test.py:", str(e))
        exit(e)
    
def write_to_comp():
    '''
    Sends the code generated by the LLM (Wizard Coder) to the Nvidia Jetson to execute.
    '''
    
    hostname = '192.168.50.211' #IP address of the Jetson
    username = 'nesl'
    password = 'nesl'

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(hostname, username=username, password=password)
        scp = ssh.open_sftp()
        scp.put(code_file_path, remote_path)
        print("File transferred successfully")
    finally:
        ssh.close()



#----------------------------- MAIN LOOPED FUNCTION ------------------
def central_loop():
    '''
    First, it runs the LLM with the prompt given and writes the Python code portion of the output to a file using the generate_code function.
    Then it sends the generated Python code file to the Jetson using the write_to_comp function.
    '''

    generate_code()
    write_to_comp()


#----------------------------- ACTIVATING LOOP ------------------
# Add the directory to the watcher
# watch_mask = pyinotify.IN_MODIFY | pyinotify.IN_CLOSE_WRITE
watch_mask = pyinotify.IN_CLOSE_WRITE
watcher_manager.add_watch(dir_to_watch, watch_mask)

# Create the notifier and associate it with the watcher and event handler
notifier = pyinotify.Notifier(watcher_manager, EventHandler())

# run once for TESTING PURPOSES
#central_loop()

# Start monitoring for file changes
try:
    print(f"Monitoring file: {task_file_path}")
    notifier.loop()
except KeyboardInterrupt:
    # Exit gracefully when interrupted by Ctrl+C
    notifier.stop()
    print("Monitoring stopped")
