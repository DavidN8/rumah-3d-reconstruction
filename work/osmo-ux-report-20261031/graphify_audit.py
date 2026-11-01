from pathlib import Path
import json,sys
from graphify.extract import extract
from graphify.build import build_from_json
from graphify.cluster import cluster,score_all
from graphify.analyze import god_nodes,surprising_connections,suggest_questions
from graphify.report import generate
from graphify.export import to_json
from graphify.diagnostics import diagnose_extraction

def main():
    root=Path(__file__).resolve().parent;code=root/'code';out=root/'graphify-out'
    detection=json.loads((out/'.graphify_detect.json').read_text());files=[Path(x) for x in detection['files']['code']]
    # Windows stdin cannot be a multiprocessing spawn entry point. Serial AST
    # extraction avoids that failed initial path and uses no external LLM.
    ast=extract(files,parallel=False)
    merged={**ast,'hyperedges':[],'input_tokens':0,'output_tokens':0}
    (out/'.graphify_ast.json').write_text(json.dumps(ast));(out/'.graphify_extract.json').write_text(json.dumps(merged))
    graph=build_from_json(merged,root=str(code),directed=False);assert graph.number_of_nodes()>30
    communities=cluster(graph);cohesion=score_all(graph,communities);gods=god_nodes(graph);surprises=surprising_connections(graph,communities)
    labels={i:'Community '+str(i) for i in communities};questions=suggest_questions(graph,communities,labels)
    assert to_json(graph,communities,str(out/'graph.json')) is not False
    (out/'GRAPH_REPORT.md').write_text(generate(graph,communities,cohesion,labels,gods,surprises,detection,{'input':0,'output':0},str(code),suggested_questions=questions),encoding='utf-8')
    analysis={'communities':{str(k):v for k,v in communities.items()},'cohesion':{str(k):v for k,v in cohesion.items()},'gods':gods,'surprises':surprises,'questions':questions}
    (out/'.graphify_analysis.json').write_text(json.dumps(analysis,default=str))
    health=diagnose_extraction(merged,directed=False,root=str(code));(out/'health.json').write_text(json.dumps(health,default=str))
    summary={'files':len(files),'nodes':graph.number_of_nodes(),'edges':graph.number_of_edges(),'communities':{str(k):[graph.nodes[n].get('label',n) for n in v[:10]] for k,v in communities.items()},'cohesion':analysis['cohesion'],'healthCounters':{k:v for k,v in health.items() if isinstance(v,(int,float,str))},'LLMInputTokens':0,'LLMOutputTokens':0,'extraction':'serial AST; initial Windows stdin multiprocessing failure superseded'}
    (out/'summary.json').write_text(json.dumps(summary,default=str,indent=2));print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
