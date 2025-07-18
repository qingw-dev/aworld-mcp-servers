import json
from datetime import datetime
import os

def get_a_trace_with_img(agent_history, tarce_info_dict):
    history_model_li=agent_history.history

    task_id=tarce_info_dict.get("task_id","")
    level=tarce_info_dict.get("level","")
    question=tarce_info_dict.get("question","")
    ground_truth=tarce_info_dict.get("ground_truth","")
    agent_answer=tarce_info_dict.get("agent_answer",{})

    final_answer=tarce_info_dict.get("final_answer","")
    score_em=tarce_info_dict.get("score_em",False)

    trace_dict={"task_id":task_id,"level":level,"question":question,"ground_truth":ground_truth}

    conversations=[]
    for idx,history_model in enumerate(history_model_li):
        a_step=json.loads(history_model.model_dump_json())
        if a_step["result"][-1]["error"] !=None:
            continue
        screenshot=a_step["state"]["screenshot"]
        action_li=[]
        for action in history_model.model_output.action:
            action_dict=json.loads(action.model_dump_json())
            for k,v in action_dict.items():
                if v is not None:
                    action_li.append({k:v})
                    break
        if idx==0:
            con_user={
                "role":"user",
                "content":{
                    "text":question,
                    "image":screenshot,
                    "snapshot":a_step["snapshot"]
                }
            }
        else:
            con_user={
                "role":"user",
                "content":{
                    "text":"<image>",
                    "image":screenshot,
                    "snapshot":a_step["snapshot"]
                }
            }
        con_assistant={
            "role":"assistant",
            "content":{
                "think":json.dumps(a_step.get("model_output",{}).get("current_state",{}),ensure_ascii=False),
                "actions":action_li,
                "action_results":[{"content":act_res.get("extracted_content",""),"error":act_res.get("error","")} for act_res in a_step.get("result",{})]
            }
        }
        conversations.append(con_user)
        conversations.append(con_assistant)
    trace_dict["conversations"]=conversations
    trace_dict["browser_answer"]=agent_answer
    trace_dict["final_answer"]=final_answer
    trace_dict["score_em"]=score_em

    return trace_dict

def get_a_trace_without_img():
    pass

def save_trace_in_oss(agent_history, tarce_info_dict, oss_client, trace_dir_name, trace_file_name):
    trace_dict=get_a_trace_with_img(agent_history, tarce_info_dict)
    trace_prefix="ml001/browser_agent/traces/"
    dict_key = os.path.join(trace_prefix,trace_dir_name,trace_file_name+".json")
    result = oss_client.upload_data(trace_dict, dict_key)
    print(f"Upload trace data: {'Success: ' + result if result else 'Failed'}")
    return result

def list_traces(oss_client, trace_file_dir):
    trace_prefix="ml001/browser_agent/traces/"
    objs=oss_client.list_objects(os.path.join(trace_prefix,trace_file_dir))
    result=[]
    for dic in objs:
        if dic["key"].endswith(".json"):
            result.append(dic["key"].split(os.path.join(trace_prefix,trace_file_dir)+"/")[-1].split(".json")[0])
    return result

def get_traces_from_oss(oss_client, trace_file_dir, trace_name_li):
    trace_prefix="ml001/browser_agent/traces/"
    result=[]
    for trace_name in trace_name_li:
        dict_key = os.path.join(trace_prefix,trace_file_dir,trace_name+".json")
        result.append({"file_name":trace_name,"data":oss_client.read_data(dict_key,True)})
    return result