from backend.app.security import verify_password
from backend.app.ai.classifier import analyze
from backend.app.ai.sentiment import predict_sentiment

def make_manager(client,email):
    from backend.app.database import SessionLocal
    from backend.app.models import User
    reg=client.post('/api/auth/register',json={'name':'Test Manager','email':email,'password':'SecurePassword123!'}).json()
    db=SessionLocal();u=db.get(User,reg['user']['id']);u.role='manager';db.commit();db.close()
    client.headers['Authorization']='Bearer '+reg['access_token']

def test_registration_login_hashing_and_jwt(client):
    data=client.post('/api/auth/register',json={'name':'Jamie Doe','email':'jamie@example.com','password':'SecurePassword123!'}).json()
    assert data['user']['role']=='customer'
    from backend.app.database import SessionLocal
    from backend.app.models import User
    db=SessionLocal();u=db.get(User,data['user']['id']);assert u.hashed_password!='SecurePassword123!';assert verify_password('SecurePassword123!',u.hashed_password);db.close()
    login=client.post('/api/auth/login',json={'email':'jamie@example.com','password':'SecurePassword123!'})
    assert login.status_code==200 and login.json()['access_token']
    client.headers['Authorization']='Bearer '+login.json()['access_token']
    assert client.get('/api/auth/me').json()['email']=='jamie@example.com'

def test_roles_protect_analytics(client,customer):
    assert client.get('/api/analytics/overview').status_code==403
    assert client.get('/api/agents').status_code==403

def test_health_frontend_assets_and_swagger(client):
    assert client.get('/api/health').json()['database']=='connected'
    assert client.get('/').status_code==200 and 'SupportIQ' in client.get('/').text
    assert client.get('/assets/app.js').status_code==200
    assert client.get('/assets/app.css').status_code==200
    schema=client.get('/openapi.json').json()
    assert '/api/tickets' in schema['paths'] and '/api/knowledge/search' in schema['paths']

def test_ticket_creation_retrieval_analysis_and_customer_close(client,customer):
    res=client.post('/api/tickets',json={'subject':'Payment failed and money deducted','description':'My card payment failed but money was deducted. Please check this payment.'})
    assert res.status_code==201
    t=res.json();assert t['category'] in ('Payment','Billing');assert t['sentiment']=='Negative';assert t['ai_confidence']>0
    detail=client.get(f"/api/tickets/{t['id']}").json();assert 'tfidf-logreg' in detail['analysis']['model_name'];assert len(detail['messages'])==1
    assert client.put(f"/api/tickets/{t['id']}/customer-status",json={'status':'Closed'}).status_code==200
    assert client.put(f"/api/tickets/{t['id']}/customer-status",json={'status':'Open'}).json()['status']=='Open'

def test_customer_ticket_isolation(client,customer):
    data=client.post('/api/tickets',json={'subject':'Account login question','description':'I cannot log into my account today.'}).json()
    client.post('/api/auth/register',json={'name':'Other Customer','email':'other@example.com','password':'SecurePassword123!'})
    other=client.post('/api/auth/login',json={'email':'other@example.com','password':'SecurePassword123!'}).json()
    client.headers['Authorization']='Bearer '+other['access_token']
    assert client.get(f"/api/tickets/{data['id']}").status_code==403

def test_agent_ticket_update_assignment_and_suggestion(client,customer):
    t=client.post('/api/tickets',json={'subject':'Product is broken','description':'My product stopped working after two weeks and I need help.'}).json()
    from backend.app.database import SessionLocal
    from backend.app.models import User
    db=SessionLocal();agent=User(name='Agent One',email='agent@example.com',role='agent',team='Technical Support',hashed_password='hashed');db.add(agent);db.commit();agent_id=agent.id;db.close()
    make_manager(client,'manager@example.com')
    assert client.put(f"/api/tickets/{t['id']}/assign",json={'agent_id':agent_id}).status_code==200
    updated=client.put(f"/api/tickets/{t['id']}",json={'priority':'High','status':'In Progress'});assert updated.json()['priority']=='High'
    s=client.post(f"/api/tickets/{t['id']}/suggest-response").json();assert s['label']=='AI Suggested Response';assert 'suggestion' in s

def test_ticket_ai_routing_fallback(client,customer):
    from backend.app.database import SessionLocal
    from backend.app.models import User
    db=SessionLocal();u=User(name='Billing Agent',email='bill@example.com',role='agent',team='Billing',hashed_password='x');db.add(u);db.commit();db.close()
    t=client.post('/api/tickets',json={'subject':'Payment declined','description':'My payment failed and the bank deducted the amount.'}).json()
    assert t['assigned_agent_id'] is not None

def test_knowledge_upload_search_and_analytics(client,customer):
    from io import BytesIO
    from docx import Document
    created=client.post('/api/tickets',json={'subject':'Refund for recent order','description':'I want to request a refund for my recent order and need the next steps.'})
    assert created.status_code==201
    make_manager(client,'manager2@example.com')
    upload=client.post('/api/knowledge/upload',files={'file':('refund-policy.txt',b'Refunds require an order number and are reviewed by the billing team.','text/plain')})
    assert upload.status_code==201
    assert upload.json()['chunks']>=1 and upload.json()['embedding_model']
    found=client.post('/api/knowledge/search',json={'query':'How are refunds reviewed?'}).json();assert found['results'] and 'billing team' in found['answer']
    passage=found['results'][0];assert passage['filename']=='refund-policy.txt' and passage['score']>0 and passage['content']
    draft=client.post(f"/api/tickets/{created.json()['id']}/suggest-response").json()
    assert draft['label']=='AI Suggested Response' and draft['sources'] and 'refund' in draft['suggestion'].lower()
    empty=client.post('/api/knowledge/search',json={'query':'quantum telescope boat engine'}).json()
    assert not empty['results'] and 'No relevant knowledge' in empty['answer']
    assert client.delete(f"/api/knowledge/{upload.json()['id']}").status_code==204
    word=Document();word.add_paragraph('Warranty coverage must be verified against the order record before replacement.');buffer=BytesIO();word.save(buffer)
    docx=client.post('/api/knowledge/upload',files={'file':('warranty-guide.docx',buffer.getvalue(),'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
    assert docx.status_code==201 and docx.json()['extraction']=='docx'
    report=client.get('/api/analytics/overview').json();assert report['total_tickets']==1;assert report['by_category']
    assert 'team_workload' in report and 'escalations_by_day' in report

def test_rule_classifier():
    a=analyze('Cannot log into account','I cannot sign in and need a password reset.')
    assert a['category']=='Account' and a['intent'] in ('account_access','password_reset') and 0<=a['confidence']<=1

def test_local_ml_pipeline_and_sentiment():
    a=analyze('Delivery is late','My package has not arrived and tracking is delayed.')
    sentiment,confidence,_=predict_sentiment('This is broken','It failed and I am upset.')
    assert a['category']=='Shipping' and a['intent']=='delivery_delay'
    assert a['language']=='English' and 0<=a['confidence']<=1
    assert sentiment=='Negative' and 0<=confidence<=1
    assert 'tfidf-logreg' in a['model_name']

def test_manager_can_edit_routing_rules_and_view_real_model_metrics(client,customer):
    make_manager(client,'routing-manager@example.com')
    teams=client.get('/api/teams');assert teams.status_code==200
    if not teams.json():client.post('/api/teams',json={'name':'Priority Billing','description':'Billing queue'})
    assert client.put('/api/routing-rules/Billing',json={'team_name':'Priority Billing','is_active':True}).status_code==200
    rules=client.get('/api/routing-rules').json();assert next(r for r in rules if r['category']=='Billing')['team_name']=='Priority Billing'
    metrics=client.get('/api/ml/evaluation');assert metrics.status_code==200
    assert metrics.json()['rows']>0 and 'f1_macro' in metrics.json()['models']['category']

def test_agent_cannot_view_ticket_assigned_to_another_agent(client,customer):
    t=client.post('/api/tickets',json={'subject':'Account login failure','description':'I cannot log into my account and need help.'}).json()
    from backend.app.database import SessionLocal
    from backend.app.models import User,Ticket
    db=SessionLocal();assigned=User(name='Assigned',email='assigned@example.com',role='agent',hashed_password='x');other=User(name='Other',email='other-agent@example.com',role='agent',hashed_password='x');db.add_all([assigned,other]);db.flush();db.get(Ticket,t['id']).assigned_agent_id=assigned.id;other_id=other.id;db.commit();db.close()
    # Use a signed token for the newly created agent.
    from backend.app.security import create_access_token
    client.headers['Authorization']='Bearer '+create_access_token(other_id,'agent')
    assert client.get(f"/api/tickets/{t['id']}").status_code==403

def test_attachment_validation_and_owner_access(client,customer):
    t=client.post('/api/tickets',json={'subject':'Upload a support log','description':'I need to attach a short text file for support.'}).json()
    uploaded=client.post(f"/api/tickets/{t['id']}/attachments",files={'file':('details.txt',b'Example support details','text/plain')})
    assert uploaded.status_code==201
    listing=client.get(f"/api/tickets/{t['id']}/attachments").json();assert listing[0]['filename']=='details.txt'
    downloaded=client.get(f"/api/tickets/{t['id']}/attachments/{uploaded.json()['id']}");assert downloaded.content==b'Example support details'
    invalid=client.post(f"/api/tickets/{t['id']}/attachments",files={'file':('payload.exe',b'nope','application/octet-stream')})
    assert invalid.status_code==400
