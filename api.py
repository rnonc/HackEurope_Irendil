from fastapi import FastAPI, WebSocket, WebSocketDisconnect,UploadFile, File, Form
from formats import *
from pydantic import ValidationError
import uvicorn,os,json
from contextlib import asynccontextmanager
from genome import GenomeChecker, Experiments
from langsmith.client import Client
from langchain_core.documents import Document
import secrets, asyncio, base64
import pandas as pd
from io import BytesIO
import PyPDF2
from dotenv import load_dotenv
load_dotenv("config.env")

__version__ = "v1.0"

# Start and close function (lifespan)
@asynccontextmanager
async def lifespan(app: FastAPI):
    api_key = os.getenv('ALPHAGENOME_KEY')
    app.checker = GenomeChecker(api_key)
    langchain = Client(api_url="https://eu.api.smith.langchain.com")
    app.prompt = langchain.pull_prompt("chrisahn99/irendil_hackeurope",include_model=True,secrets={"GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY")})
    app.prompt_pdf = langchain.pull_prompt("jeanpierre/stool_image_analysis",include_model=True,secrets={"GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY")}
)


    yield

    del app.checker
    

# App déjà définie
app = FastAPI(lifespan=lifespan, title="Irendil API",
              description="HackEurope: Proof of concept Microbiota analysis",
              version=__version__)


# Token statique pour l'exemple
VALID_TOKEN = os.getenv('VALID_TOKEN')

@app.get("/")
def read_root():
    return {"message": "Irendil API"}

@app.post("/pdf_loading")
async def pdf_loading(file: UploadFile = File(...),token: str = Form(...)):
    if token != VALID_TOKEN:
        return {"error": "Token invalide"}

    content = await file.read()
    pdf_reader = PyPDF2.PdfReader(BytesIO(content))
    text = "\n".join(page.extract_text() for page in pdf_reader.pages if page.extract_text())
    prompt_value = app.prompt_pdf.invoke({"stool_file": text,"list_of_bacterias":list(app.checker.knowledge['bacteria'])})
    result = json.loads(prompt_value.content.replace('```json','').replace('```','').replace("None","null"))
    return {"analysis": result}

@app.websocket("/ws/stool_analysis")
async def experiments_ws(websocket: WebSocket):
    await websocket.accept()

    try:
        # Premier message du client : JSON avec token et paramètres
        stool_data = await websocket.receive_json()
        
        try:
            params = Stool(**stool_data)
        except ValidationError as e:
            await websocket.send_json({"error": "Paramètres invalides", "details": e.errors()})
            await websocket.close(code=1003)  # unsupported data
            return

        # Vérification du token
        if params.token != VALID_TOKEN:
            await websocket.send_json({"error": "Token invalide"})
            await websocket.close(code=1008)
            return

        # Crée l'objet Experiments
        stool = params.stool
        dataframe_exps:pd.DataFrame = app.checker.stool_analysis(stool)
        targets = list(dataframe_exps['promoter_interval'])
        full_contexts = list(dataframe_exps['context_interval'])
        gens = list(dataframe_exps['target_gene'])
        experiments:Experiments = app.checker.exps(targets, full_contexts, gens)
        outputs = []
        if len(dataframe_exps) >0:
            line = dataframe_exps.iloc[0]
            output_line = {"bacteria":line['bacteria'],"target_gene":line['target_gene'],"metabolite":line["metabolite"],
                        "activation_hypothesis":line["activation_hypothesis"],"bacteria_abundance":stool[line['bacteria']]}
            await websocket.send_json({"task":"start_exp","data":output_line})
            await asyncio.sleep(0.01) 
            # Stream des résultats
            for i,score in enumerate(experiments):
                await asyncio.sleep(0.01)    
                line = dataframe_exps.iloc[i]
                output_line["reaction_score"] = score
                output_line["macro_level_effect"]=line['macro_level_effect']
                outputs.append(output_line)
                
                await websocket.send_json({"task":"return_exp","data":output_line})
                await asyncio.sleep(0.01)  
                if i +1 < len(dataframe_exps):
                    line = dataframe_exps.iloc[i+1]
                    output_line = {"bacteria":line['bacteria'],"target_gene":line['target_gene'],"metabolite":line["metabolite"],
                        "activation_hypothesis":line["activation_hypothesis"],"bacteria_abundance":stool[line['bacteria']]}
                    await websocket.send_json({"task":"start_exp","data":output_line})
                    await asyncio.sleep(0.01)
            await asyncio.sleep(0.01) 
            await websocket.send_json({"task":"start_clinical_insight"})
            await asyncio.sleep(0.01) 
            prompt_value = app.prompt.invoke({"patient_id": 1, "microbial_data_json":outputs})
            clean_data = json.loads(prompt_value.content,strict=False)
            await websocket.send_json({"task":"end_clinical_insight","data":clean_data})
        
        else:
            await websocket.send_json({"error":"no relevant experience"})
        

    except WebSocketDisconnect:
        print("Client déconnecté")
    except Exception as e:
        await websocket.send_json({"error": str(e)})
    finally:
        await websocket.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)