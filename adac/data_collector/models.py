'''Data Models to Store'''
import json
from adac.data_collector import DB
from peewee import Model, CharField, DateTimeField, IntegerField, IntegrityError

class BaseModel(Model):
    '''A base model which sets up the database connection for all inherited classes
    '''
    class Meta:
        database = DB # Database for customers

    def __str__(self):
        r = {}
        for k in self._data.keys():
            try:
                r[k] = str(getattr(self, k))
            except:
                r[k] = json.dumps(getattr(self, k))
        return str(r)

class ConsensusData(BaseModel):
    node_name = CharField()
    timestamp = DateTimeField()
    data = CharField()
    experiment_id = CharField()


class Event(BaseModel):

    node_name = CharField()
    timestamp = DateTimeField()
    event_name = CharField()
    event_data = CharField()
    iteration = IntegerField()
    experiment_id = CharField()

    @classmethod
    def create_new(cls, node_name, timestamp, event_name, event_data, iteration, experiment_id):
        '''Creates a new object'''
        try:
            cls.create(
                node_name=node_name,
                timestamp=timestamp,
                event_name=event_name,
                event_data=event_data,
                iteration=iteration,
                experiment_id=experiment_id)
        except IntegrityError:
            raise ValueError("timestamp already exists")


class Statistic(BaseModel):

    timestamp = DateTimeField()
    node_name = CharField()
    statistic_type = CharField()
    statistic_value = CharField()
    iteration = IntegerField()
    experiment_id = CharField()

    @classmethod
    def create_new(cls, node_name, timestamp, statistic_type, statistic_value, iteration, experiment_id):
        '''Creates a new object'''
        try:
            cls.create(
                node_name=node_name,
                timestamp=timestamp,
                statistic_type=statistic_type,
                statistic_value=statistic_value,
                iteration=iteration,
                experiment_id=experiment_id)
        except IntegrityError:
            raise ValueError("Couldn't Create Row")

