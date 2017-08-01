import adac.util as u
import threading
username = 'pi'
data_loc = '/home/pi/adac/vec.txt'
hosts = ['192.168.2.177',
	 '192.168.2.178',
	 '192.168.2.180',
	 '192.168.2.181',
	 '192.168.2.182', 
         '192.168.2.183',
         '192.168.2.184']

def cpy_id(usr, hst1, hst2):
	u.run(usr, hst1, ['ssh-copy-id {}@{}'.format(usr, hst2)])

thd = []
for host in hosts:
	for hostx in hosts:
#		t = threading.Thread(target=cpy_id, args=(username, host, hostx))
#		t.start()
		u.run(username, host, ['ssh-copy-id {}@{}'.format(username, hostx)])

#for thred in thd:
#	thred.join()

#print(u.generate_data(username, hosts, data_loc, 25))
#print(u.generate_data('pi', ['raspberrypi', 'daredevil'], '/home/pi/vec.txt', 10))

