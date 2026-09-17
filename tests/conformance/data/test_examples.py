from fractions import Fraction

from gsm_memory.evaluation.formulas import auto_accept, cancel_rate, rating_condition, revenue_charge


def test_ex01_ex25_reference_expectations():
    actual=[revenue_charge(200000),revenue_charge(280000),revenue_charge(300000),"not_applicable","insufficient_evidence","insufficient_evidence",auto_accept("bike_partner",Fraction(49,100)),auto_accept("bike_partner",Fraction(1,2)),"insufficient_evidence",rating_condition(Fraction(97,20)),rating_condition(Fraction(49,10)),"insufficient_evidence",revenue_charge(200000),revenue_charge(240000),revenue_charge(240000),"unresolved_conflict","insufficient_evidence",True,False,False,"customer_request_time","completed_delivery_points",cancel_rate(2,8),True,"insufficient_evidence"]
    expected=[16000,0,0,"not_applicable","insufficient_evidence","insufficient_evidence",True,False,"insufficient_evidence",False,True,"insufficient_evidence",16000,8000,8000,"unresolved_conflict","insufficient_evidence",True,False,False,"customer_request_time","completed_delivery_points",Fraction(1,5),True,"insufficient_evidence"]
    assert actual == expected
