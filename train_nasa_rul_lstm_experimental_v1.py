"""Cell-held-out LSTM RUL experiment. Writes only to a new release directory.

Install the optional dependency with: .venv/Scripts/python.exe -m pip install -r requirements-experimental.txt
Run: .venv/Scripts/python.exe train_nasa_rul_lstm_experimental_v1.py --version lstm-rul-v1
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.io import loadmat
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error
import torch
from torch import nn

ROOT=Path(__file__).resolve().parent
CELLS=("B0005","B0006","B0018")
FEATURES=("cycle_number","ambient_temperature_C","discharge_capacity_Ah","soh_percent","previous_soh_percent","capacity_change_from_previous_Ah")
SEQ=12
EOL=1.4

def read_cell(cell):
    obj=loadmat(ROOT/'data'/'nasa'/f'{cell}.mat',simplify_cells=True)[cell]
    rows=[]
    for e in np.atleast_1d(obj['cycle']):
        if str(e.get('type','')).lower()!='discharge': continue
        d=e.get('data') or {}
        try: cap=float(np.asarray(d['Capacity']).reshape(-1)[0])
        except (KeyError,TypeError,ValueError,IndexError): continue
        if np.isfinite(cap) and cap>0: rows.append((float(e.get('ambient_temperature',np.nan)),cap))
    f=pd.DataFrame(rows,columns=['ambient_temperature_C','discharge_capacity_Ah'])
    f['cycle_number']=np.arange(1,len(f)+1,dtype=float)
    f['soh_percent']=f.discharge_capacity_Ah/f.discharge_capacity_Ah.iloc[0]*100
    f['previous_soh_percent']=f.soh_percent.shift(1)
    f['capacity_change_from_previous_Ah']=f.discharge_capacity_Ah.diff()
    return f.dropna().reset_index(drop=True)

class Net(nn.Module):
    def __init__(self,n):
        super().__init__(); self.lstm=nn.LSTM(n,16,batch_first=True); self.head=nn.Sequential(nn.Linear(16,8),nn.ReLU(),nn.Linear(8,1))
    def forward(self,x): return self.head(self.lstm(x)[0][:,-1]).squeeze(-1)

def sequences(frame, scaler, train=False):
    x=scaler.transform(frame[list(FEATURES)]).astype('float32')
    end=np.flatnonzero(frame.discharge_capacity_Ah.to_numpy()<=EOL)
    if not len(end): return [],[]
    e=int(end[0]); xs=[]; ys=[]
    for i in range(SEQ-1,e+1):
        xs.append(x[i-SEQ+1:i+1]); ys.append(float(e-i))
    return xs,ys

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--version',default='lstm-rul-v1'); args=ap.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}',args.version): raise ValueError('Invalid version')
    out=ROOT/'models'/'releases'/args.version
    if out.exists(): raise FileExistsError(f'Refusing to overwrite {out}')
    torch.manual_seed(42); np.random.seed(42); torch.set_num_threads(1)
    frames={c:read_cell(c) for c in CELLS}; results=[]; fold_models=[]
    for held in CELLS:
        train_cells=[c for c in CELLS if c!=held]
        scaler=StandardScaler().fit(pd.concat([frames[c].loc[:int(np.flatnonzero(frames[c].discharge_capacity_Ah.to_numpy()<=EOL)[0]),list(FEATURES)] for c in train_cells]))
        tx=[]; ty=[]
        for c in train_cells:
            x,y=sequences(frames[c],scaler)
            tx.extend(x); ty.extend(y)
        vx,vy=sequences(frames[held],scaler)
        if not tx or not vx: raise ValueError('Insufficient complete trajectories for sequence length')
        model=Net(len(FEATURES)); opt=torch.optim.Adam(model.parameters(),lr=.005,weight_decay=.001); loss=nn.SmoothL1Loss()
        X=torch.tensor(np.asarray(tx)); Y=torch.tensor(ty,dtype=torch.float32)
        model.train()
        for _ in range(80):
            opt.zero_grad(); err=loss(model(X),Y); err.backward(); opt.step()
        model.eval()
        with torch.no_grad(): pred=model(torch.tensor(np.asarray(vx))).numpy()
        pred=np.maximum(pred,0); mae=float(mean_absolute_error(vy,pred)); rmse=float(np.sqrt(mean_squared_error(vy,pred)))
        results.append({'held_out_cell':held,'train_cells':train_cells,'sequence_length':SEQ,'n_test_windows':len(vy),'mae_cycles':mae,'rmse_cycles':rmse})
        fold_models.append((held,model,scaler))
    # Fit final research artifact on all complete cells; does not become active inference model.
    scaler=StandardScaler().fit(pd.concat([frames[c].loc[:int(np.flatnonzero(frames[c].discharge_capacity_Ah.to_numpy()<=EOL)[0]),list(FEATURES)] for c in CELLS]))
    fx=[]; fy=[]
    for c in CELLS:
        x,y=sequences(frames[c],scaler); fx.extend(x); fy.extend(y)
    model=Net(len(FEATURES)); opt=torch.optim.Adam(model.parameters(),lr=.005,weight_decay=.001); loss=nn.SmoothL1Loss(); X=torch.tensor(np.asarray(fx)); Y=torch.tensor(fy,dtype=torch.float32)
    model.train()
    for _ in range(80): opt.zero_grad(); err=loss(model(X),Y); err.backward(); opt.step()
    out.mkdir(parents=True,exist_ok=False); torch.save({'state_dict':model.state_dict(),'feature_order':FEATURES,'sequence_length':SEQ,'scaler_mean':scaler.mean_.tolist(),'scaler_scale':scaler.scale_.tolist()},out/'nasa_rul_lstm_experimental.pt')
    summary={'version':args.version,'status':'experimental_not_default','target':'cycles to first measured capacity <= 1.4 Ah','training_cells':list(CELLS),'right_censored_cells':['B0007'],'sequence_length':SEQ,'folds':results,'macro_cell_mae_cycles':float(np.mean([r['mae_cycles'] for r in results])),'macro_cell_rmse_cycles':float(np.mean([r['rmse_cycles'] for r in results])),'limitations':['Only three complete independent NASA cell trajectories; each fold trains on two cells.','One fixed seed and a small cohort; results are exploratory, not a robust model-selection claim.','B0007 is right-censored and excluded from standard supervised fitting.','Laboratory cell data do not validate field EV packs or second-life safety.']}
    (out/'evaluation.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8'); print(json.dumps(summary,indent=2))
if __name__=='__main__': main()
