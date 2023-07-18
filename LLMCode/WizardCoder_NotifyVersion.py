# Libraries
import time
from transformers import AutoTokenizer, AutoModelForCausalLM
import os
import pyinotify
import paramiko

# load tokenizer and model
tokenizer = AutoTokenizer.from_pretrained("WizardLM/WizardCoder-15B-V1.0")
#model = AutoModelForCausalLM.from_pretrained("WizardLM/WizardCoder-15B-V1.0").to("cuda")
model = AutoModelForCausalLM.from_pretrained("WizardLM/WizardCoder-15B-V1.0", device_map='auto')
#model = AutoModelForCausalLM.from_pretrained("WizardLM/WizardCoder-15B-V1.0", device_map='sequential', max_memory={0: '49 GiB'}, revision='main', low_cpu_mem_usage = True, offload_folder='offload')
print("Model Loaded")

prompt_file_path = '/home/pragya/LLMCode/prompt.txt'
code_file_path = '/home/pragya/LLMCode/LLM_generated_code.py'

dir_to_watch = os.path.abspath('/home/pragya/LLMCode')
watcher_manager = pyinotify.WatchManager()

# Define the event handler
class EventHandler(pyinotify.ProcessEvent):
    '''
    def process_IN_MODIFY(self, event):
        file_path = os.path.join(event.path, event.name)
        if file_path == prompt_file_path:
            print(f"File: {prompt_file_path} is being modified...")
    '''
    def process_IN_CLOSE_WRITE(self, event):
        file_path = os.path.join(event.path, event.name)
        if file_path == prompt_file_path:
            # Process the file update event
            cur_time = time.ctime(time.time())
            print(f"File updated: {file_path} at {cur_time}")
            generate_code(file_path)
            
            
def write_to_comp():
	hostname = '192.168.50.211'
	username = 'nesl'
	password = 'nesl'

	local_path = '/home/pragya/LLMCode/LLM_generated_code.py'
	remote_path = '/home/nesl/desktopTransferredCode.py'

	ssh = paramiko.SSHClient()
	ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

	try:
		ssh.connect(hostname, username=username, password=password)
		scp = ssh.open_sftp()
		scp.put(local_path, remote_path)
		print("File transferred successfully")
	finally:
		ssh.close()

def generate_code(prompt_file_path):        
    print("Running model.")
    # read from prompt file
    try:
        with open (prompt_file_path, 'r') as prompt_file:
            prompt = prompt_file.read()
    except Exception as e:
        print("Error when read from file prompt.txt:", str(e)) 
        exit(e)
    start_time = time.time()
    # tokenize prompt and model generate
    try:
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

    # save to code file
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
    end_time = time.time()
    time_used = end_time - start_time
    print("Finish Generating Code:", time_used)
    write_to_comp()


# Add the directory to the watcher
# watch_mask = pyinotify.IN_MODIFY | pyinotify.IN_CLOSE_WRITE
watch_mask = pyinotify.IN_CLOSE_WRITE
watcher_manager.add_watch(dir_to_watch, watch_mask)

# Create the notifier and associate it with the watcher and event handler
notifier = pyinotify.Notifier(watcher_manager, EventHandler())

# run once
generate_code(prompt_file_path)


# Start monitoring for file changes
try:
    print(f"Monitoring file: {prompt_file_path}")
    notifier.loop()
except KeyboardInterrupt:
    # Exit gracefully when interrupted by Ctrl+C
    notifier.stop()
    print("Monitoring stopped")
    


    
    

