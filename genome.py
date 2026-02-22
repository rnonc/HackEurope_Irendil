
from alphagenome.data import genome as gn
from alphagenome.models import dna_client
from alphagenome.models.variant_scorers import GeneMaskActiveScorer
import numpy as np
import pandas as pd

class Experiments:
    def __init__(self,targets:list[str],full_contexts:list[str],gens:list[str],ag_client:dna_client.DnaClient,variant=None):
        self.its = zip(targets,full_contexts,gens)
        self.ag_client = ag_client
        self.variant = variant
    
    def exp(self,target:gn.Interval,full_context:gn.Interval,gen_name:str,variant=None):
        active_scorer = GeneMaskActiveScorer(
            requested_output=dna_client.OutputType.CAGE # We want to see the protein expression change
        )

        ism_results = self.ag_client.score_ism_variants(
            interval=full_context,
            ism_interval=target,
            interval_variant=variant,
            variant_scorers=[active_scorer],
            organism=dna_client.Organism.HOMO_SAPIENS,
            progress_bar=False

        )

        anndata_obj = ism_results[0][0]
        gene_index = anndata_obj.obs[anndata_obj.obs['gene_name'] == gen_name].index[0]

        active_score = anndata_obj.X[int(gene_index)]

        output = np.nanmax(active_score).item()

        return output
    
    def __iter__(self):
        for target_str, full_context_str, gen in self.its:
            target = gn.Interval.from_str(target_str)
            full_context = gn.Interval.from_str(full_context_str)
            for threshold in [dna_client.SEQUENCE_LENGTH_16KB,dna_client.SEQUENCE_LENGTH_100KB,dna_client.SEQUENCE_LENGTH_500KB,dna_client.SEQUENCE_LENGTH_1MB]:
                if threshold > full_context.width:
                    break
            try:
                yield self.exp(target, full_context.resize(threshold), gen, self.variant)
            except:
                yield None

class GenomeChecker:
    def __init__(self,api_key:str,data_path:str='data'):
        self.data_path = data_path
        self.ag_client = dna_client.create(api_key)
        self.knowledge = pd.read_csv("data/experiments/irendil_knowledge_data.csv")

    def stool_analysis(self,stool:dict[str,float]):
        planned_experiments = self.knowledge.copy()
        planned_experiments = planned_experiments[planned_experiments['bacteria'].isin(stool.keys())]
        
        return planned_experiments


    def exps(self,targets:list[str],full_contexts:list[str],gens:list[str],variant=None):
        return Experiments(targets,full_contexts,gens,self.ag_client,variant)
        



        
    

        