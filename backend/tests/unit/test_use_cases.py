from datetime import UTC, datetime
import asyncio
import pytest
from application.errors.exceptions import DuplicateSubscriptionError, SubjectInactiveError, SubscriptionLimitExceededError
from application.services import NotificationService
from application.templates.code_template_provider import CodeTemplateProvider
from application.use_cases.use_cases import GetPublicSubjectPageUseCase, PollExternalEventsUseCase, SubscribeUserToSubjectUseCase
from domain.entities.models import Subscription, Subject, TaskEvent, User
from domain.value_objects.enums import ChannelType, EventType, Source, SubjectType

class SubRepo:
    def __init__(self): self.items=[]
    def list_active_by_user(self,u): return [x for x in self.items if x.user_id==u and x.is_active]
    def list_active_by_subject(self,s): return [x for x in self.items if x.subject_id==s and x.is_active]
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

class EventRepo:
    def __init__(self): self.items=[]
    def save(self,event): self.items.append(event)
    def list_latest_by_subject(self,subject_id,limit=10): return [x for x in self.items if x.subject_id==subject_id][:limit]

class Provider:
    def __init__(self,events): self.events=events
    async def fetch_events(self,date_from,date_to): return self.events

class UserRepo:
    def __init__(self,items): self.items=items
    def get_by_id(self,user_id): return self.items.get(user_id)
    def save(self,user): self.items[user.user_id]=user

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

def test_notification_service_resolves_channel_user_id():
    prepo=PRepo(); ch=Channel()
    users=UserRepo({'u1': User('u1', ChannelType.MAX, channel_user_id='max-user-1')})
    svc=NotificationService(prepo,Registry(ch),CodeTemplateProvider(),users)
    event=TaskEvent('e1','s1',Source.REGIONCITY,EventType.CLEANING_COMPLETED,datetime.now(UTC),{'subject_title':'A'})

    sent=svc.notify_users(event,['u1'])

    assert sent==1
    assert ch.sent[0].user_id=='max-user-1'

def test_polling_saves_events_and_can_suppress_backfill_notifications():
    event=TaskEvent('e2','s1',Source.REGIONCITY,EventType.CLEANING_COMPLETED,datetime.now(UTC),{'subject_title':'A'})
    event_repo=EventRepo(); sub=SubRepo(); sub.save(Subscription('sub1','u1','s1'))
    prepo=PRepo(); ch=Channel(); notifier=NotificationService(prepo,Registry(ch),CodeTemplateProvider())
    uc=PollExternalEventsUseCase(Provider([event]),event_repo,sub,notifier,prepo)

    result=asyncio.run(uc.execute(datetime.now(UTC),datetime.now(UTC),notify=False))

    assert result['saved_count']==1
    assert result['sent_count']==0
    assert result['suppressed_notification_count']==1
    assert event_repo.items[0].external_id=='e2'
    assert ch.sent==[]
