from peewee import SqliteDatabase
from adac.data_collector import DB
from adac.data_collector.models import Statistic
from matplotlib import pyplot as plt
import numpy as np
import json

fig_size = []
fig_size.append(12)
fig_size.append(9)
plt.rcParams["figure.figsize"] = fig_size

s = Statistic.select(Statistic.experiment_id).distinct()
experiments = [i.experiment_id for i in s]
exp_ids = [x.experiment_id for x in s]

s = Statistic.select(Statistic.statistic_type).distinct()
stat_types = [x.statistic_type for x in s]

s = Statistic.select(Statistic.node_name).distinct()
nodes = [x.node_name for x in s]

def memcache_db():
    # First let's load all the data into memory. This will take some time...

    # Make sure we reset to get the old database
    Statistic._meta.database = SqliteDatabase('dc.db')

    # Create a new in-memory database (but don't link it yet)
    memdb = SqliteDatabase(':memory:')

    # Select all of the records. list() ensures that the query isn't executed lazily.
    records = Statistic.select().execute() # Let's grab ALL the records
    records = list(records)
    num_rec_bef = len(records)

    # Set the statistic database to be the new database and insert our records.
    Statistic._meta.database = memdb
    Statistic.create_table(fail_silently=True)
    for x in list(records):
        Statistic.insert(json.loads(str(x).replace("'", '"'))).execute()

    # Check to make sure we've got all the records and that we're using the in-mem DB
    num_rec = Statistic.select().count()
    print(Statistic._meta.database.database)
    return num_rec == num_rec_bef

def display(data_dict, title=None):
    '''Display a graph of the differential statistics'''
    for key in data_dict:
        iters = range(len(data_dict[key]))
        plt.plot(iters, data_dict[key], label=key)

    plt.legend(ncol=2)
    if title is not None:
        plt.title(title)
    plt.show()

def display_absolutes(exp_id, stat_type, ip):
    '''Display a graph of the absolute statistics'''
    data = Statistic.select().where(Statistic.experiment_id == exp_id, Statistic.statistic_type == stat_type, Statistic.node_name == ip).order_by(Statistic.timestamp.asc())
    # Let's parse the stat data
    stats = {}
    for x in data:
        stats[x.iteration] = {}
        for y in x.statistic_value.split(','):
            z = y.strip().split('=')
            stats[x.iteration][z[0]] = float(z[1])


    iterations = list(stats.keys())
    gfields = list(stats[0])
    # Remove a field if necessary
    # gfields.pop(gfields.index('idle'))

    # Plot everything that we can
    for y in gfields:
        l1 = []
        for x in iterations:
            l1.append(stats[x][y])
        plt.plot(iterations, l1, label=y)

    # Create and modify legend if necessary
    plt.legend(ncol=2)
    plt.title('Analysis for {} {}\'s\n\n'.format(exp_id, stat_type))
    plt.show()

def get_data(exp_id, stat_type, ip):
    #print("Using {}".format(Statistic._meta.database.database))
    data = Statistic.select().where(Statistic.experiment_id == exp_id, Statistic.statistic_type == stat_type, Statistic.node_name == ip).order_by(Statistic.timestamp.asc())
    # Let's parse the stat data
    stats = {}
    
    # Setup the dictionary
    max_iter = -1
    for x in data:
        if x.iteration > max_iter:
            max_iter = x.iteration
    for y in data[0].statistic_value.split(','):
            z = y.strip().split('=')
            stats[z[0]] = [0]*max_iter
    for x in data:
        for y in x.statistic_value.split(','):
            z = y.strip().split('=')
            stats[z[0]][x.iteration-1] = float(z[1])
    return stats
    
    
def get_data_diffs(exp_id, stat_type, ip):
    stats = get_data(exp_id, stat_type, ip)
    iterations = len(stats[list(stats.keys())[0]])
    gfields = list(stats.keys())
    # Remove a field if necessary
    # gfields.pop(gfields.index('idle'))

    # Plot everything that we can
    for y in stats:
        for i in reversed(range(len(stats[y]))):
            stats[y][i] = stats[y][i] - stats[y][i-1]
        stats[y][0] = 0.0
    return stats

def get_data_diffbegin(exp_id, stat_type, ip):
    stats = get_data(exp_id, stat_type, ip)
    iterations = len(stats[list(stats.keys())[0]])
    gfields = list(stats.keys())
    # Remove a field if necessary
    # gfields.pop(gfields.index('idle'))

    # Plot everything that we can
    for y in stats:
        for i in reversed(range(len(stats[y]))):
            stats[y][i] = stats[y][i] - stats[y][0]
        stats[y][0] = 0.0
    return stats

def get_avgs(function, base_stat, sub_stat):
    #average of bytes sent over all topologies for each node 
    Adata = {}
    for n in nodes:
        Adata[n] = {}
        for k in exp_ids:
            Adata[n][k] = np.average(function(k, base_stat, n)[sub_stat])
    avgs = {}
    for n in nodes:
        avgs[n] = [0, 0]
        for k in exp_ids:
            if 'NO_MPI' in k:
                avgs[n][0] += Adata[n][k]
            else:
                avgs[n][1] += Adata[n][k]
        avgs[n][0] /= 5
        avgs[n][1] /= 5
    for n in nodes:
        print("Node: {}  |  NON_MPI: {:1.5f}  |  MPI: {:1.5f}  | {} ".format(n, avgs[n][0], avgs[n][1], avgs[n][0] < avgs[n][1]))
    return avgs

def get_avgs_graphs(id_list, function, base_stat, sub_stat):
    #average of bytes sent over all topologies for each node 
    Adata = {}
    for n in nodes:
        Adata[n] = {}
        for k in exp_ids:
            Adata[n][k] = np.average(function(k, base_stat, n)[sub_stat])
    avgs = {}
    for n in nodes:
        avgs[n] = [0, 0]
        for k in id_list:
            if 'NO_MPI' in k:
                avgs[n][0] += Adata[n][k]
            else:
                avgs[n][1] += Adata[n][k]
        avgs[n][0] /= 5
        avgs[n][1] /= 5
    for n in nodes:
        print("Node: {}  |  NON_MPI: {:1.5f}  |  MPI: {:1.5f}  | {} ".format(n, avgs[n][0], avgs[n][1], avgs[n][0] < avgs[n][1]))
    return avgs

def print_list_statistics(data, title=None):
    if title is None:
        title = "{} for list: {:3.4f}"
    else:
        title = "{} " + 'for {0}:'.format(title) + ' {:3.4f}'
    print(title.format("Average", np.average(data)))
    print(title.format("Median", np.median(data)))
    print(title.format("Minimum", np.min(data)))
    print(title.format("Maximum", np.max(data)))
    print(title.format("Standard Deviation", np.std(data)))
    print(title.format("Variance", np.var(data)))
    
    


    