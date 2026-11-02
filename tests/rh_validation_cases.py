from unittest.mock import patch
import pandas as pd
import pytest
from modules.rh import service
from core.strict_reads import DataReadError

@pytest.mark.parametrize('employee,start,end', [('SIM-RH-009','2026-11-01','2026-11-02'),('missing','2026-11-01','2026-11-02'),('SIM-RH-001','bad','2026-11-02'),('SIM-RH-001','2026-11-03','2026-11-02')])
def test_no_write_for_invalid_request(employee,start,end):
    records=pd.DataFrame([{'employe_id':'SIM-RH-001','actif':'OUI'},{'employe_id':'SIM-RH-009','actif':'NON'}])
    with patch.object(service,'get_employes',return_value=records), patch.object(service,'insert_hybrid') as insert:
        with pytest.raises(ValueError): service.create_demande_conge(employee,start,end,'simulation')
        insert.assert_not_called()

def test_read_failure_propagates_without_write():
    with patch.object(service,'fetch_data',side_effect=DataReadError('failure')), patch.object(service,'insert_hybrid') as insert:
        with pytest.raises(DataReadError): service.create_demande_conge('SIM-RH-001','2026-11-01','2026-11-02','simulation')
        insert.assert_not_called()

def test_valid_request_writes_once_to_mock():
    with patch.object(service,'get_employes',return_value=pd.DataFrame([{'employe_id':'SIM-RH-001','actif':'OUI'}])), patch.object(service,'insert_hybrid') as insert:
        service.create_demande_conge('SIM-RH-001','2026-11-01','2026-11-02','simulation')
        assert insert.call_count==1
