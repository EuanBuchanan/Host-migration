'''migrate.py
Usage:
    migrate.py init <initcsv>  [--CONFDIR=switchports]
                                [--CONFILE=switchports.yaml]
    migrate.py mark <finalcsv> [--CONFDIR=switchports]
                                [--CONFILE=switchports.yaml]
    migrate.py move <source> <destination> [--CONFDIR=switchports]
                                           [--CONFILE=switchports.yaml]
                                           [--RUNDIR=rundir]
                                           [--RUNSHEET=runsheet.csv]
    migrate.py update <updatecsv> [--CONFDIR=switchports]
                                [--CONFILE=switchports.yaml]
                                [--UPDATEDIR=updated_switchports]
                                [--UPDATEFILE=updated_switchport.yaml]
    migrate.py status <switch> [<port>] <status>  [--CONFDIR=switchports]
                                                  [--CONFILE=switchports.yaml]
    migrate.py final <source> <destination> [--CONFDIR=switchports]
                                           [--CONFILE=switchports.yaml]
                                           [--RUNDIR=rundir]
                                           [--RUNSHEET=runsheet.csv]

Options:
    --CONFDIR=DIR      Directory where file storing state infromation of interfaces
                       is stored. [default: switchports]
    --CONFILE=FILE     Filename storing state information of interfaces,
                       generated by migrate.py init [default: switchports.yaml]
    --RUNSHEET=FILE    Filename of runsheet generated by move commmand
                       [default: runsheet.csv]
    --RUNDIR=DIR       Direcotryu where runsheet generated by move command is
                       stored [default: rundir]
    --UPDATEDIR=DIR    Direcotry where updated state information of interfaces
                       [default: updated_switchports]
    --UPDATEFILE=FILE  Filename of updated state information of interfaces
                       [default: updated_switchport.yaml]

'''

#!/usr/bin/env python
# -*- coding: utf-8 -*-
from collections import defaultdict
from collections import OrderedDict
from docopt import docopt
from pathlib import Path
import copy
import csv
import errno
import logging.config
import operator
import pprint as pp
import os
import yaml


def setup_logging(
    default_path='access_6_logging.yaml',
    default_level=logging.INFO,
    env_key='LOG_CFG'
    ):
    """Setup logging configuration

    """
    path = default_path
    value = os.getenv(env_key, None)
    if value:
        path = value
    if os.path.exists(path):
        with open(path, 'rt') as f:
            config = yaml.safe_load(f.read())
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=default_level)


class SwitchPort():
    '''
    Class holds information about unique Switch / interface combinations.

    For the purpose of migrating hosts from one access switch to another,
    there are a few fields we care about.

    switch_id:      String of the switch name
    port_id:        Sting of the switch port
    status :        String of the status the port is in, determined by a manual show run
    vlan:           String of the vlan the port is configured for
    description:    String of the interface description

    Other fields used in the class are:

    configuration:  String which has the configuration required to change an
                    interface.
    final='' :      Default string of the final switch for the host.

    '''

    def __init__(self, switch_id, port_id, status, vlan, description, configuration = '',
            final=''):

        self.switch_id = switch_id
        self.port_id = port_id
        self.status = status
        self.vlan = vlan
        self.description = description
        self.configuration = configuration
        self.final = final

def get_switchports_d(initcsv, confdir,confile):
    '''
    Takes in path and filename of csv file.
    Populates dictionary with instances of SwitchPort

    Parameters
    ----------
    initcsv: csv file with headers switch_id, port, status, vlan, description
    confdir: directory yaml file will be stored in
    confile: filename of yaml file

    Returns
    -------
    None

    Calls
    -----
    dump_switchports(switchports_d, confile, condir)
    '''

    logger = logging.getLogger()
    switchports_d = dict()

    logger.info('File: %s', initcsv)
    with open(initcsv) as csvfile:
        reader = csv.reader(csvfile)
        next(reader) #skip headers
        for row in reader:
            switch_id, port, status, vlan, description = row
            if switch_id not in switchports_d.keys():
                switchports_d[switch_id] = dict()
            switchports_d[switch_id][port] = SwitchPort(switch_id, port,
                    status, vlan, description)
        logger.debug('row: %s', row)
    logger.debug('switchport dictionary: %s ', pp.pformat(switchports_d))
    dump_switchports(switchports_d, confdir, confile)

def dump_switchports(switchports_d, confdir, confile):

    '''
    Dumps instances of Switchport to a yaml file.

    Parameters
    ----------
    switchports_d : dictionary of dictionaries, each subdictionary is
            ('<interface>', SwitchPort())
    confdir: string passed by docopt, the direcotry the file will be saved in
    confile: string passed by docopt, the filename that instances of SwitchPort
            will be saved in
    Returns
    -------
    None

    '''
    logger = logging.getLogger()
    switchport_file = os.path.join(
                    os.getcwd(), confdir, confile)
    logging.info('switchport_file: %s', switchport_file)
    os.makedirs(os.path.dirname(switchport_file), exist_ok=True)
    with open(switchport_file, 'w') as outfile:
            yaml.dump(switchports_d, outfile, default_flow_style=False)
    print('Switchport configuration generated, stored in directory', confdir,
        ', file', confile)

def load_switchports(confdir,confile):

    '''
    Loads instances of SwitchPort from a yaml file.

    Parameters
    ----------
    confdir: string passed by docopt, the directory the file will be read from
    confile: string passed by docopt, the yaml file with instances of
        SwitchPort

    Returns
    -------
    switchports_d : dictionary of dictionaries, each subdictionary is
            ('<interface>', SwitchPort())
    '''
    logger = logging.getLogger()
    switchports_file = os.path.join(confdir, confile)
    with open(switchports_file, 'r') as infile:
        switchports_d = yaml.load(infile)
    logger.debug('switchport dictionary: %s ',
    pp.pformat(switchports_d))
    logger.info('### Loaded SwitchPort dictionary from Dir %s, file %s',
                confdir, confile)
    return switchports_d

def mark_switchports_final(finalcsv, confdir, confile):

    '''
    Critical hosts have been assigned to specific switches. At the end of the
    task, hosts needto be on the correct switch.

    Function takes in a csv file and writes it to a list.

    Parameters
    ----------
    finalcsv: string passed by docopt, relative path where csv file is located.
                Matching on switch and port as there are multiple duplicate
                descriptions. Current switch[1], migrate to switch[2], current
                port [3]
                index 0 is the host and index 2 is the final switch.
    confdir: string passed by docopt, directory where the yaml file with
                instances of SwitchPort will is loaded from
    confile: string passed by docopt, file with instances of SwitchPort

    Returns
    -------
    None

    Mutates
    -------
    switchports_d

    Calls
    -----
    dump_switchports
    '''

    logger=logging.getLogger()
    logging.info('### Getting switchport dictionary ###')
    switchports_d = load_switchports(confdir,confile)
    logger.debug('switchports_d: %s', pp.pformat(switchports_d))
    logger.info('Getting Final State information')
    with open(finalcsv) as infile:
        logging.info('Opened CSV %s', finalcsv)
        reader = csv.reader(infile)
        next(reader)
        count = 0
        for row in reader:
            cur_switch, cur_port, final_switch =\
                    row[1], row[3], row[2]
            switchports_d[cur_switch][cur_port].final = final_switch
            count += 1
            logger.debug('Switch:%s, port:%s marked with final:%s',\
                    cur_switch, cur_port, final_switch)
    logging.info('%s ports marked', count)
    dump_switchports(switchports_d, confdir, confile)

def get_available_port_d(switchports_d, *switch_ids):

    '''
    Get available ports so they can be allocated for moving.

    Parameters
    ----------
    switchports_d : dictionary of dictionaries, each subdictionary is
            ('<interface>', SwitchPort())
    switch_ids: tuple of strings
    Examples:
        'distsw_31'
        'distsw_32'

    Returns
    -------
    available_ports_d : dictionary of dictionaries, each subdictionary is
            ('<interface>', SwitchPort())
    '''
    logger=logging.getLogger()
    logger.info('Allocating disabled ports')
    available_ports_d = dict()
    for each in range(len(switch_ids[0])):
        switch_id = switch_ids[0][each]
        available_ports_d[switch_id] = dict()
        logging.debug('switch_id: %s', switch_id)
        for port, values in switchports_d[switch_id].items():
            status = values.status
            if status == 'disabled':
                available_ports_d[switch_id][port] = values
    logger.debug('available_ports_d: %s', pp.pformat(available_ports_d))
    return(available_ports_d)

def match_final_state(switchports_d, sorted_available_ports_d,
    source_t, destination_t):

    '''
    Matches attritbute final of instances of SwitchPort, with
    to_switch. If matched, it pass off to configure_ports with port from
    available_ports_d

    Parameters
    ----------
    switchports_d : dictionary of dictionaries, each subdictionary is
            ('<interface>', SwitchPort())
    available_ports_d : dictionary of dictionaries, each subdictionary is
            ('<interface>', SwitchPort())
            source_t: string of comma separated switch IDs
            destination_t: string of comma separated switch IDs

    Returns
    -------
    final_run_sheet : list of elements:
        from_port.switch_id : string
        from_port.port_id : string
        disable_config : string
        to_port.switch_id : string
        to_port.port_id : string
        from_port.vlan : string
        enable_config : string
        Final : 'Final'

    '''


    logger = logging.getLogger()
    return_run_sheet = []
    count = 0
    for source in source_t:
        for source_port, source_value in switchports_d[source].items():
            # if source_value.final is in destination_t and matches its own
            # switch_id, it's in the right place
            if source_value.final in destination_t and\
                    source_value.final != source_value.switch_id:
                logger.debug('source_value.final: %s, source_vlaue.switch_id %s,\
                        destination_t, %s', pp.pformat(source_value.final),\
                        pp.pformat(source_value.switch_id), pp.pformat(destination_t))
                count += 1
                logging.debug('source_port.final %s, count %s', source_value.final, count)
                source_value.status = 'disabled'
                switchports_d[source][source_port] = source_value
                logging.debug('new status %s', switchports_d[source][source_port].status)
                if len(sorted_available_ports_d[source_value.final].keys()) > 0:
                    to_port = sorted_available_ports_d[source_value.final].popitem()[1]
                    ports = (source_value, to_port)
                    configured_ports = configure_ports(ports)
                    configured_ports.append('Final')
                    return_run_sheet.append(configured_ports)
    logging.info('%s ports matched to final switch', count)
    return(return_run_sheet, sorted_available_ports_d, switchports_d)

def get_enable_port(old_switch, old_port, new_switch, new_port, vlan, description):

    '''
    Generate enable port configuration.

    Parameters
    ----------

    old_switch : string
    old_port: string
    new_switch: string
    new_port: string
    vlan: string
    description : string

    Returns
    -------
    enable_port_config : string

    '''

    logger = logging.getLogger()
    logger.debug('Getting enable config')
    enable_port_config = \
    '! Move ' + old_switch + ':' + old_port +  'to' +\
        new_switch + ':' + new_port + '\n' +\
    '!show interface ' + new_port + 'status' + '\n' +\
    '! If status is disabled, proceed with configuration\n' +\
    'conf t\n' +\
    ' interface ' + new_port + '\n' +\
    ' description ' + description + '\n' +\
    ' switchport access vlan ' + vlan + '\n' +\
    ' switchport trunk encapsulation dot1q\n' +\
    ' switchport mode access\n' +\
    ' switchport nonegotiate\n' +\
    ' switchport port-security maximum 3\n' +\
    ' switchport port-security\n' +\
    ' switchport port-security aging time 2\n' +\
    ' switchport port-security violation restrict\n' +\
    ' switchport port-security aging type inactivity\n' +\
    ' srr-queue bandwidth share 1 42 53 4\n' +\
    ' srr-queue bandwidth shape 300 0 0 0\n' +\
    ' priority-queue out\n' +\
    ' spanning-tree portfast\n' +\
    ' service-policy input ACCESS-CONDTRUST-PMAP\n' +\
    ' no shut\n' +\
    ' end\n' +\
    '!\n'

    return(enable_port_config)

def get_disable_port(old_switch, old_port, new_switch, new_port, vlan, description):

    '''
    Generate disable port configuration.

    Parameters
    ----------

    old_switch : string
    old_port: string
    new_switch: string
    new_port: string
    vlan: string
    description : string

    Returns
    -------
    disable_port_config : string

    '''
    logger = logging.getLogger()
    logger.debug('Getting disable config')
    disable_port_config = \
    '! disable configuration for ' + old_switch + ':' + old_port + '\n' +\
    'show interface ' + old_port + 'status' + '\n' +\
    '! If notconnect and patch has been moved, disable\n' +\
    'conf t\n' +\
    ' interface ' + old_port + '\n' +\
    ' description disabled\n' +\
    ' shutdown\n' +\
    ' end\n' +\
    '!\n'

    return(disable_port_config)

def configure_ports(ports):

    '''
    Configure ports, return list of configuruations.

    Parameters
    ----------
    ports: tuple
        (from_port, to_port)
        from_port: instance of SwitchPorts
        to_port: instance of SwitchPorts

    Returns
    -------
    run_sheet_list: list of elements:

        from_port.switch_id : string
        from_port.port_id : string
        disable_config : string
        to_port.switch_id : string
        to_port.port_id : string
        from_port.vlan : string
        enable_config : string

    Mutates
    -------
    Instances of SwitchPort
    '''
    logger = logging.getLogger()
    logger.debug('Generating port configurations')
    from_port, to_port = ports[0], ports[1]
    run_sheet = []
    # Generate the run sheet
    disable_config = get_disable_port(from_port.switch_id,
            from_port.port_id, to_port.switch_id, to_port.port_id,
            from_port.vlan, from_port.description)
    enable_config = get_enable_port(from_port.switch_id,from_port.port_id,
            to_port.switch_id, to_port.port_id, from_port.vlan,
            from_port.description)
    run_sheet_list = ([from_port.description,from_port.switch_id, from_port.port_id,
        disable_config, to_port.switch_id, to_port.port_id, from_port.vlan,
        enable_config])
    return(run_sheet_list)


def move_interfaces(rundir, runsheet, confdir, confile, source, destination):

    '''
    Function generates enable and disable configuation for moving interfaces from one or more switches to one ore more
    switches.

    First, SwitchPorts.final is checked. If destination switch matches, an interface from that switch is allocated. All
    other interfaces are distributed evenly over the destination switches.

    Parameters
    ----------
    rundir:         string, passed by docopt.
                    The directory to save the run sheet to.
    runsheet:       string, passed by docopt.
                    The file to save the run sheet to.
    confdir:        string, passed by docopt.
                    The directory that instances of SwitchPort are stored in.
    confile:        string, passed by docopt.
                    The file that instances of SwitchPort are saved to.
    source:         string, passed by docopt.
                    Comma separated list of switch ids
    destination:    string, passed by docopt.
                    Comm separated list of switch ids

    Returns
    -------
    None

    Calls
    -----
    load_switchports(confdir, confile)
    get_available_port_d(switchports_d, destination_t)
    '''

    logger = logging.getLogger()
    logger.debug(print(rundir, runsheet, confdir,confile, source, destination))

    # Load the switchport dictionary.
    switchports_d = load_switchports(confdir, confile)

    # Need turn $source and $destination in to tuples
    source_t = tuple(source.split(','))
    destination_t = tuple(destination.split(','))

    # Need a dict of swtichports that are available for hosts to move to
    available_ports_d = get_available_port_d(switchports_d, destination_t)
    logger.info('Recieved dictionary available_ports_d')

    # Sort the dictionary so that the run is repeatable, as dictonaries are random
    sorted_available_ports_d = dict()
    for destination_id in destination_t:
        logging.debug('Sorting dictionary key %s ', destination_id)
        sorted_available_ports_d[destination_id] = OrderedDict(
                sorted(available_ports_d[destination_id].items(),
                key=lambda t: t[0]))
    logger.debug('Sorted Dictionary %s', pp.pformat(sorted_available_ports_d))

    # Match final destinations before allocating randomly
    run_sheet_l, sorted_available_ports_d, switchports_d = \
    match_final_state(switchports_d, sorted_available_ports_d,
    source_t, destination_t)
    # Match rest of the ports

    # Get number of available ports on each swtich so that hosts not allocated
    # to a specific port can be distributed evenly
    count = 0
    dst_max_l = []
    for dst in destination_t:
        dst_max_l.append((len(sorted_available_ports_d[dst].values())))
        logger.debug('dst_max_l: %s', pp.pformat(dst_max_l))
    for source in source_t:
        for source_port in switchports_d[source].values():
            logger.debug('source_port.vlan: %s source_port.status %s',source_port.vlan, source_port.status)
            if (source_port.vlan == '1296' or source_port.vlan == '1297') \
                    and source_port.status != 'disabled':
                count += 1
                logger.debug('Matched %s with %s, count: %s', source_port.vlan,
                        source_port.status, count)

               # Index returned by below matches the switch string in
               # desination_t and its place in dst_max_l
                max_dst_idx = dst_max_l.index(max(dst_max_l))
                dst_max_l[max_dst_idx] -= 1
                logging.debug('max_dst_idx: %s, dst_max_l %s',max_dst_idx,
                        dst_max_l)
                to_port =\
                  sorted_available_ports_d[destination_t[max_dst_idx]].popitem()[1]
                logger.debug('source_port %s, to_port: %s',
                        pp.pformat(to_port), pp.pformat(to_port))
                ports = (source_port, to_port)
                run_sheet_l.append(configure_ports(ports))
    logging.info('%s not mached to final swtich', count)
    write_csv_file(run_sheet_l, rundir, runsheet)

def write_csv_file(runsheet, outdir, outname):
    '''
    Writes a list to csv_file.

    Parametes
    ---------
    filename :  string, name of the csv file
    outdir:     string, name of output directory
    outname:    string, name of output file

    Returns
    -------
    None
    '''

    logger = logging.getLogger()
    # Create directory if required.
    path_filename = os.getcwd() + '/' + outdir + '/' + outname
    logging.debug('path_filename: %s', path_filename)
    os.makedirs(os.path.dirname(path_filename), exist_ok=True)
    # Write csv file
    logging.info('Writing %s to dir %s', outname, outdir)
    with open(path_filename, 'w', newline='') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(['Description','From Switch','From Interface',
                         'Disable Configuration', 'To Switch',
                         'To Interface', 'vlan', 'Enable Configuration'])
        for row in runsheet:
            writer.writerow(row)

def update_switchports(updatecsv, confdir, confile, updatedir, updatefile):

    '''
    Load switchport state. Update switchport state from CSV Save switchport
    state.

    Parameters
    ----------
    condir:      string, the dirctory where existing switchport state information is
                 stored
    confile:     string, the name of the file storing swtichport state
    updatedir:   string, name of the directory where updated switchport state is
                 written.
    updatefile:  string, name of the file storing switchport state

    Returns
    -------
    None
    '''
    logger = logging.getLogger()
    logger.info('Loading switchport state from dir: %s, file %s',confdir,
            confile)
    switchports_d = load_switchports(confdir, confile)
    logger.debug('switchports_d: ', pp.pformat(switchports_d))
    path_filename = os.getcwd() + '/' + updatedir + '/' + updatefile
    logging.debug('path_filename: %s', path_filename)
    os.makedirs(os.path.dirname(path_filename), exist_ok=True)
    # Read csv file
    logging.info('Reading %s from dir %s', updatedir, updatefile)
    with open(updatecsv, 'r', newline='') as csv_file:
        reader = csv.reader(csv_file)
        # skip headers
        next(reader)
        for row in reader:
            description, from_switch, from_port, to_switch, to_port, vlan = \
                    row[0], row[1], row[2], row[4], row[5], row[6]
            
            old = switchports_d[from_switch][from_port]
            new = switchports_d[to_switch][to_port]

            logger.debug('old port: %s, new port = %s', old, new)
           
            logger.debug( 'Original NEW: new.vlan %s, new.description, %s, new.status, %s, new.final, %s',new.vlan, new.description, new.status, new.final)
            
            # Need to move the final attribute with the rest of the config
            # Do this first as .final on the old interface is getting blanked
            new.vlan, new.description, new.status, new.final =\
                    vlan, description, 'connected', old.final
            logger.debug('Updated NEW: new.vlan %s, new.description, %s, new.status, %s, new.final %s',new.vlan, new.description, new.status, new.final)

            logger.debug('Original OLD: old.vlan %s, old.description, %s, old.status, %s, old.final %s',old.vlan, old.description, old.status, old.final)
            #Blank everything, it's a free port now
            old.vlan, old.description, old.status, old.final =\
            '','', 'disabled',''
            logger.debug('Updated OLD: old.vlan %s, old.description, %s,old.status, %s, old.final %s', old.vlan, old.description, old.status, old.final)
    dump_switchports(switchports_d, updatedir, updatefile)


def finalize(rundir, runsheet, confdir, confile, source, destination):

    '''
    Function matches PortSwitch.final of hosts being moved with
    PortSwitch.switch_id of available port switches and returns configuration
    to both enable the new port and disable the old port.

    Parameters
    ----------
    rundir:         string, passed by docopt.
                    The directory to save the run sheet to.
    runsheet:       string, passed by docopt.
                    The file to save the run sheet to.
    confdir:        string, passed by docopt.
                    The directory that instances of SwitchPort are stored in.
    confile:        string, passed by docopt.
                    The file that instances of SwitchPort are saved to.
    source:         string, passed by docopt.
                    Comma separated list of switch ids
    destination:    string, passed by docopt.
                    Comm separated list of switch ids

    Returns
    -------
    None

    Calls
    -----
    load_switchports(confdir, confile)
    get_available_port_d(switchports_d, destination_t)
    '''

    logger = logging.getLogger()
    logger.debug(print(rundir, runsheet, confdir,confile, source, destination))

    # Load the switchport dictionary.
    switchports_d = load_switchports(confdir, confile)

    # Need turn $source and $destination in to tuples
    source_t = tuple(source.split(','))
    destination_t = tuple(destination.split(','))

    # Need a dict of swtichports that are available for hosts to move to
    available_ports_d = get_available_port_d(switchports_d, destination_t)
    logger.info('Recieved dictionary available_ports_d')

    # List for the run sheet
    run_sheet_l = list()

    # Sort the dictionary so that the run is repeatable, as dictonaries are random
    sorted_available_ports_d = dict()
    for destination_id in destination_t:
        logging.debug('Sorting dictionary key %s ', destination_id)
        sorted_available_ports_d[destination_id] = OrderedDict(
            sorted(available_ports_d[destination_id].items(),
                   key=lambda t: t[0]))
    logger.debug('Sorted Dictionary %s', pp.pformat(sorted_available_ports_d))

    # Match final destinations before allocating randomly
    run_sheet_l, sorted_available_ports_d, switchports_d = \
        match_final_state(switchports_d, sorted_available_ports_d,
                          source_t, destination_t)
    write_csv_file(run_sheet_l, rundir, runsheet)

def main(docopt_args):
    """ main-entry point for program, expects dict with arguments from docopt() """

    # Notice, no checking for -h, or --help is written here.
    logger = logging.getLogger()
    logger.debug('Docopt Dictionary: %s', pp.pformat(args))
    # docopt will automagically check for it and use your usage string.

    if docopt_args['init']:
        get_switchports_d(docopt_args['<initcsv>'],
                          docopt_args['--CONFDIR'],
                          docopt_args['--CONFILE']
                          )
    elif docopt_args['mark']:
       mark_switchports_final(docopt_args['<finalcsv>'],
                              docopt_args['--CONFDIR'],
                              docopt_args['--CONFILE'])
    elif docopt_args['move']:
        move_interfaces( docopt_args['--RUNDIR'],
                            docopt_args['--RUNSHEET'],
                            docopt_args['--CONFDIR'],
                            docopt_args['--CONFILE'],
                            docopt_args['<source>'],
                            docopt_args['<destination>'])
    elif docopt_args['update']:
        update_switchports( docopt_args['<updatecsv>'],
                            docopt_args['--CONFDIR'],
                            docopt_args['--CONFILE'],
                            docopt_args['--UPDATEDIR'],
                            docopt_args['--UPDATEFILE'])
    elif docopt_args['final']:
        finalize( docopt_args['--RUNDIR'],
                            docopt_args['--RUNSHEET'],
                            docopt_args['--CONFDIR'],
                            docopt_args['--CONFILE'],
                            docopt_args['<source>'],
                            docopt_args['<destination>'])

    #     load_switchports()

if __name__ == '__main__':

    setup_logging()

    # Docopt will check all arguments, and exit with the Usage string if they
    # don't pass.  If you simply want to pass your own modules documentation
    # then use __doc__, otherwise, you would pass another docopt-friendly usage
    # string here.  You could also pass your own arguments instead of sys.argv
    # with: docopt(__doc__, argv=[your, args])

    args = docopt(__doc__)

    # We have valid args, so run the program.
    main(args)
