from datetime import UTC, datetime
import pytest
from application.errors.exceptions import DuplicateSubscriptionError, SubjectInactiveError, SubscriptionLimitExceededError
from application.services import NotificationService
from application.templates.code_template_provider import CodeTemplateProvider
from application.use_cases.use_cases import GetPublicSubjectPageUseCase, SubscribeUserToSubjectUseCase
from domain.entities.models import Subscription, Subject, TaskEvent
from domain.value_objects.enums import EventType, Source, SubjectType

class SubRepo:
    def __init__(self): self.items=[]
    def list_active_by_user(self,u): return [x for x in self.items if x.user_id==u and x.is_active]
    def get_active(self,u,s): return next((x for x in self.items if x.user_id==u and x.subject_id==s and x.is_active),None)
    def save(self,s): self.items.append(s)
    def deactivate(self,u,s): ...
    def deactivate_all(self,u): return 0

class SubjectRepo:
    def __init__(self,active=True): self.active=active
    def get_by_id(self,sid): return Subject(sid,SubjectType.ENTRANCE,'E',is_active=self.active)

class CacheRepo:
    def __init__(self): self.d={}
    def get(self,k): return self.d.get(k)
    def set(self,k,v,t): self.d[k]=v

class PRepo:
    def __init__(self): self.done=set()
    def is_processed(self,source,eid,event_type): return (source,eid,event_type) in self.done
    def mark_processed(self,source,eid,event_type,at): self.done.add((source,eid,event_type))

class Channel:
    def __init__(self,fail_for=None): self.sent=[]; self.fail_for=fail_for
    def send(self,p):
        if p.user_id==self.fail_for: raise RuntimeError()
        self.sent.append(p)

class Registry:
    def __init__(self,ch): self.ch=ch
    def get(self,name): return self.ch

def test_subscription_limit():
    sub=SubRepo(); subj=SubjectRepo(); uc=SubscribeUserToSubjectUseCase(subj,sub)
    for i in range(20): sub.save(Subscription(str(i),'u1',f's{i}'))
    with pytest.raises(SubscriptionLimitExceededError): uc.execute(Subscription('x','u1','s100'))

def test_duplicate_subscription():
    sub=SubRepo(); subj=SubjectRepo(); uc=SubscribeUserToSubjectUseCase(subj,sub)
    sub.save(Subscription('1','u1','s1'))
    with pytest.raises(DuplicateSubscriptionError): uc.execute(Subscription('2','u1','s1'))

def test_inactive_subject():
    uc=SubscribeUserToSubjectUseCase(SubjectRepo(active=False),SubRepo())
    with pytest.raises(SubjectInactiveError): uc.execute(Subscription('1','u1','s1'))

def test_public_page_cache_hit_miss():
    uc=GetPublicSubjectPageUseCase(CacheRepo())
    calls={'n':0}
    def fetch(_,__): calls['n']+=1; return [{'id':1}]
    uc.execute('s1',fetch); uc.execute('s1',fetch)
    assert calls['n']==1

def test_processed_event_skip_and_failure_continue():
    prepo=PRepo(); ch=Channel(fail_for='u2')
    svc=NotificationService(prepo,Registry(ch),CodeTemplateProvider())
    event=TaskEvent('e1','s1',Source.REGIONCITY,EventType.CLEANING_COMPLETED,datetime.now(UTC),{'subject_title':'A'})
    sent=svc.notify_users(event,['u1','u2','u3'])
    assert sent==2
    assert svc.notify_users(event,['u1'])==0
