# Host-migration
A command line program that generates Cisco IOS configurations for moving hosts between access switches

## Problem
In order to avoid a costly planned network outage, it's necessary to move mission crtical hosts from switch(es) that are being upgraded to spare ports on swtich(es) that are not being upgraded. Doing this manually is error-prone and time-consuming.

## Approach

The state of the access switches is populated from initial manual work, generating a CSV from a combination of:

    show interface description
    show interface status

The resulting CSV file populates a dictionary of instances of the class, SwitchPort.

Docopt is used to pass CLI arguments to the program. The options are:

* init
  Populates instances of SwitchPort, which is saved to a YAML file for persistance. 
* final
  Marks the .final value of instances of SwitchPort with the switch that the current configuration should be on. This is necessary to make sure that at the completion of all moves, hosts are distributed across the access switches in line with operational resilience requirements.
* move
  Moves mission critical hosts from switch(es) to switch(es)
* Update
  Uses the runsheet generated by 'move' to update the YAML file. This approach was taken in case there were changes from the output to that which actually took place during the migration of hosts
* Status
  [Not implemented] Query a YAML file for how many ports are free and how many mission critical ports are configured
* flatten
  [Not implemented] Ensure all instances of SwitchPort match the switch configured with .final.
  

