import pandas as pd
import pytest
from core.indicateurs_stocks import stock_value, below_threshold, expiry_alerts
from core.strict_reads import DataReadError
from modules.dashboards import service

@pytest.mark.parametrize('cost',[None,'bad',float('inf'),-1])
def test_unknown_cost_not_zero(cost):
    with pytest.raises(DataReadError):
        stock_value(pd.DataFrame([dict(quantite_disponible=2,cmp_actuel=cost)]),'cmp_actuel')

def test_zero_stock_needs_no_cost_and_known_cost_is_used():
    assert stock_value(pd.DataFrame([dict(quantite_disponible=0)]),'cmp_actuel')==0
    assert stock_value(pd.DataFrame([dict(quantite_disponible=2,cmp_actuel=3)]),'cmp_actuel')==6

@pytest.mark.parametrize('refs',[[],[dict(mp_id='other',stock_mini=5)],[dict(mp_id='M',stock_mini=None)],
    [dict(mp_id='M',stock_mini=5)]*2])
def test_missing_or_ambiguous_threshold(refs):
    with pytest.raises(DataReadError):
        below_threshold(pd.DataFrame([dict(mp_id='M',quantite_disponible=1)]),pd.DataFrame(refs))

def test_threshold_counts_only_real_below_threshold_rows():
    assert below_threshold(pd.DataFrame([dict(mp_id='M',quantite_disponible=1)]),pd.DataFrame([dict(mp_id='M',stock_mini=2)]))==1

def test_expired_today_future_and_undated_lots():
    rows=[dict(lot_id=str(i),quantite_restante=q,date_peremption=d) for i,(q,d) in enumerate([
        (1,'2026-10-01'),(1,'2026-11-02'),(1,'2026-12-02'),(1,'2026-12-03'),(1,None),(0,None)])]
    alerts,unknown=expiry_alerts(pd.DataFrame(rows),'2026-11-02 18:00',30)
    assert alerts['lot_id'].tolist()==['0','1','2'] and unknown==1

def test_invalid_known_expiry_not_silently_skipped():
    with pytest.raises(DataReadError):
        expiry_alerts(pd.DataFrame([dict(quantite_restante=1,date_peremption='invalid')]),'2026-11-02',30)

@pytest.fixture
def data(monkeypatch):
    tables={}
    monkeypatch.setattr(service,'fetch_data',lambda t:tables.get(t,[]))
    return tables

def crm(data):
    return service.get_kpis_crm(pd.Timestamp('2026-11-01'),pd.Timestamp('2026-11-30'))

def opportunity(status,**kw):
    return dict(dict(statut=status,valeur_estimee=100,probabilite_pct=50,date_creation='2026-11-02',commercial_id='C'),**kw)

@pytest.mark.parametrize('status',['Nouveau','Contacté','En Négociation','NOUVELLE','EN_COURS','QUALIFICATION','PROPOSITION'])
def test_form_and_legacy_open_statuses(data,status):
    data['pipeline']=[opportunity(status,date_creation='2026-10-01')]
    assert crm(data)['pipeline_pondere']==50

@pytest.mark.parametrize('won,lost',[('Gagné','Perdu'),('GAGNEE','PERDUE')])
def test_created_cohort_not_revenue_or_closing_date(data,won,lost):
    data['pipeline']=[opportunity(won,commercial_id=None),opportunity(lost),opportunity(won,date_creation='2026-10-01')]
    k=crm(data)
    assert k['taux_conversion']==50 and k['pipeline_pondere']==0
    assert k['performance_commerciaux'].to_dict('records')==[{'Commercial':'Non attribué','Valeur estimée gagnée':100}]

@pytest.mark.parametrize('changes',[dict(statut='UNKNOWN'),dict(valeur_estimee=None),dict(probabilite_pct=101),dict(probabilite_pct=-1)])
def test_bad_crm_data_is_not_false_zero(data,changes):
    row=opportunity('Nouveau');row.update(changes);data['pipeline']=[row]
    with pytest.raises(DataReadError):crm(data)

def test_rh_active_flag_and_missing_service(data):
    data['employes']=[dict(actif='OUI',service='Production'),dict(actif='OUI',service=None),dict(actif='NON',service='Ventes')]
    k=service.get_kpis_rh(None,None)
    assert k['effectif_actif']==2
    assert k['repartition_service']['Effectif'].sum()==2
    assert 'Non renseigné' in k['repartition_service']['Service'].tolist()

@pytest.mark.parametrize('row',[dict(service='S'),dict(actif=None),dict(actif='UNKNOWN')])
def test_rh_unknown_active_not_counted(data,row):
    data['employes']=[row]
    with pytest.raises(DataReadError):service.get_kpis_rh(None,None)
