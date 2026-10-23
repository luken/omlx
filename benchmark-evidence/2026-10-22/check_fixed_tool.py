# SPDX-License-Identifier: Apache-2.0
"""macai02 Qwen3.8 localhost:8001 HTTP comparison; positional argument labels the arm."""
import ast,concurrent.futures,hashlib,json,pathlib,sys,time,urllib.request
EXPECTED_SOURCE='"""\nCase 00. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 01. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 02. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 03. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 04. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 05. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 06. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 07. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 08. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 09. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 10. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 11. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 12. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 13. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 14. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 15. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 16. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 17. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 18. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 19. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 20. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 21. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 22. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 23. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 24. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 25. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 26. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 27. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 28. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 29. A stable fixture verifies that streamed arguments preserve every character in this module.\n"""\n\ndef identity(x):\n    return x'
arm=sys.argv[1];base='http://127.0.0.1:8000';model='qwen3.8-27b'
KEY=json.loads((pathlib.Path.home()/'.omlx/settings.json').read_text())['auth']['api_key']
HEADERS={'Content-Type':'application/json','Authorization':'Bearer '+KEY}
tool={'type':'function','function':{'name':'write','description':'Write a complete Python module.','parameters':{'type':'object','properties':{'content':{'type':'string'}},'required':['content']}}}
cases={'long_tool':('Call write exactly once. Its content must be an exact copy of the Python source between BEGIN_SOURCE and END_SOURCE below, excluding those marker lines. Preserve every character and newline. Do not summarize, edit, or add a trailing newline. Use the tool, no prose.\nBEGIN_SOURCE\n"""\nCase 00. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 01. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 02. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 03. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 04. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 05. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 06. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 07. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 08. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 09. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 10. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 11. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 12. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 13. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 14. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 15. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 16. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 17. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 18. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 19. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 20. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 21. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 22. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 23. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 24. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 25. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 26. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 27. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 28. A stable fixture verifies that streamed arguments preserve every character in this module.\nCase 29. A stable fixture verifies that streamed arguments preserve every character in this module.\n"""\n\ndef identity(x):\n    return x\nEND_SOURCE',1536,True)}
def run(case,repeat,phase):
 prompt,limit,tools=cases[case];body={'model':model,'messages':[{'role':'user','content':prompt}],'max_tokens':limit,'temperature':0,'stream':True,'stream_options':{'include_usage':True},'chat_template_kwargs':{'enable_thinking':False}}
 if tools:body['tools']=[tool]
 start=time.perf_counter();first=None;first_argument=None;events=0;wire=0;usage=None;finish=None;args=[];text=[];ids=set();name='';reasoning=[]
 with urllib.request.urlopen(urllib.request.Request(base+'/v1/chat/completions',data=json.dumps(body).encode(),headers=HEADERS),timeout=300) as r:
  for line in r:
   wire+=len(line)
   if not line.startswith(b'data: '):continue
   raw=line[6:].strip()
   if raw==b'[DONE]':break
   d=json.loads(raw);assert 'error' not in d,d;events+=1
   if d.get('usage'):usage=d['usage']
   for choice in d.get('choices',[]):
    finish=choice.get('finish_reason') or finish;delta=choice.get('delta',{})
    if delta.get('content'):
     text.append(delta['content'])
     if first is None:first=time.perf_counter()-start
    if delta.get('reasoning_content'):reasoning.append(delta['reasoning_content'])
    for tc in delta.get('tool_calls') or []:
     assert tc['index']==0,tc
     if tc.get('id'):ids.add(tc['id'])
     f=tc.get('function',{});name+=f.get('name','');part=f.get('arguments','')
     if part:
      args.append(part)
      if len(part)>1 and first_argument is None:first_argument=time.perf_counter()-start
 elapsed=time.perf_counter()-start
 assert not reasoning
 output=''.join(args if tools else text)
 if tools:
  assert finish=='tool_calls' and len(ids)==1 and name=='write',(finish,ids,name)
  parsed=json.loads(output);assert parsed['content']==EXPECTED_SOURCE, 'Model did not copy fixed source exactly'
  compile(parsed['content'],'<bench-tool>','exec')
  docstring=ast.get_docstring(ast.parse(parsed['content']))
  assert docstring and len(docstring.split())>=100
  docstring_words=len(docstring.split())
 assert usage
 return {'arm':arm,'phase':phase,'case':case,'repeat':repeat,'seconds':elapsed,'first_argument_seconds':first_argument,'first_text_seconds':first,'events':events,'argument_fragments':len(args),'wire_bytes':wire,'output_chars':len(output),'output_sha256':hashlib.sha256(output.encode()).hexdigest(),'usage':usage,'valid':True,'finish_reason':finish,'docstring_words':docstring_words if tools else None}

# Exclude model load and the initial native-kernel warmup from measured time.
warmup={'model':model,'messages':[{'role':'user','content':'Reply OK.'}],'max_tokens':8,'temperature':0,'chat_template_kwargs':{'enable_thinking':False}}
with urllib.request.urlopen(urllib.request.Request(base+'/v1/chat/completions',data=json.dumps(warmup).encode(),headers=HEADERS),timeout=180) as response:
 json.load(response)
print(json.dumps(run("long_tool", int(sys.argv[2]), "fixed_output")), flush=True)
