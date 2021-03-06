
import os
import time
import shutil
import logging
import subprocess
import tempfile

import yaml
import json

from agent_exceptions import ShellException, BadConfigurationException

logger = logging.getLogger(__name__)

class AppScaleState(object):
    DEFAULT_NUM_RETRIES = 5

    @classmethod
    def config_path(cls):
        """
        Returns the configuration path to the default appscale config
        directory
        """
        # Legacy
        return os.path.join(os.path.expanduser('~'), '.appscale')
        
    @classmethod
    def private_key(cls, keyname):
        return os.path.join(cls.config_path(), keyname)

    @classmethod
    def public_key(cls, keyname):
        return "{0}.pub".format(cls.private_key(keyname))

    @classmethod
    def ssh_key(cls, keyname):
        return os.path.join(cls.config_path(), "{0}.key".format(keyname))

    @classmethod
    def write_key_file(cls, location, contents):
        # TODO: should this be 'wc'? Doesn't this imply that the file exists?
        with open(location, 'w') as f:
            f.write(contents)
        os.chmod(location, 0600)

    @classmethod
    def get_client_secrets_location(cls, keyname):
        """Returns the path on the local filesystem where the GCE
           client secrets JSON file can be found.

        Args:
          keyname: A str representing the SSH keypair name used for
                   this AppScale deployment.
        Returns:
          A str that corresponds to a location on the local filesystem where the
          client secrets file can be found.
        """
        return os.path.join(cls.config_path(), "{0}-secrets.json".format(keyname))

    @classmethod
    def get_oauth2_storage_location(cls, keyname):
        return os.path.join(cls.config_path(), "{0}-oauth2.dat".format(keyname))

    @classmethod
    def locations_json_location(cls, keyname):
        """Determines the location where the JSON file can be found that
        contains information related to service placement.
        (e.g., where machines can be found and what services they run).

        Args:
          keyname: A str that indicates the name of the SSH keypair that
                   uniquely identifies this AppScale deployment.
        Returns:
          A str that indicates where the locations.json file can be found.
        """
        return os.path.join(cls.config_path(), "locations-{0}.json".format(keyname))

    @classmethod
    def locations_yaml_location(cls, keyname):
        return os.path.join(cls.config_path(), "locations-{0}.yaml".format(keyname))

    @classmethod
    def generate_rsa_key(cls, keyname, is_verbose):
        """Generates a new RSA public and private keypair, and saves it to the
        local filesystem.
        
        Args:
          keyname: The SSH keypair name that uniquely identifies this AppScale
                   deployment.
          is_verbose: A bool that indicates if we should print the ssh-keygen
                      command to stdout.
        """

        private_key = cls.private_key(keyname)
        public_key = cls.public_key(keyname)

        if os.path.exists(public_key):
            os.remove(public_key)
            
        if os.path.exists(private_key):
            os.remove(private_key)
                
        cls.shell("ssh-keygen -t rsa -N '' -f {0}".format(private_key),
                  is_verbose)

        os.chmod(public_key, 0600)  # Note public key is generated by ssh-keygen
        os.chmod(private_key, 0600)
        shutil.copy(private_key, private_key + '.key')
        return public_key, private_key

    #
    # Configuration
    #
    @classmethod
    def get_group(cls, keyname):
        """Reads the locations.json file with key 'infrastructure_info' to see
        what security group was created for this AppScale deployment.

        Args:
          keyname: The SSH keypair name that uniquely identifies this AppScale
            deployment.
        Returns:
          The name of the security group used for this AppScale deployment.
        """
        return cls.get_infrastructure_option(tag="group", keyname=keyname)

    @classmethod
    def get_project(cls, keyname):
        """Reads the locations.json file with key 'infrastructure_info' to see
        what project ID is used to interact with Google Compute Engine in this
        AppScale deployment.

        Args:
          keyname: The SSH keypair name that uniquely identifies this AppScale
            deployment.
        Returns:
          A str containing the project ID used for this AppScale deployment.
        """
        return cls.get_infrastructure_option(tag="project", keyname=keyname)

    @classmethod
    def get_zone(cls, keyname):
        """Reads the locations.json file with key 'infrastructure_info' to see
        what zone instances are running in throughout this AppScale deployment.

        Args:
          keyname: The SSH keypair name that uniquely identifies this AppScale
            deployment.
        Returns:
          A str containing the zone used for this AppScale deployment.
        """
        return cls.get_infrastructure_option(tag="zone", keyname=keyname)

    @classmethod
    def get_subscription_id(cls, keyname):
        """ Reads the locations.json file with key 'infrastructure_info' to see
        what subscription ID is used to interact with Microsoft Azure in this
        AppScale deployment.

        Args:
          keyname: The SSH keypair name that uniquely identifies this AppScale
            deployment.
        Returns:
          A str containing the subscription ID used for this AppScale deployment.
        """
        return cls.get_infrastructure_option(tag="azure_subscription_id",
                                             keyname=keyname)

    @classmethod
    def get_app_id(cls, keyname):
        """ Reads the locations.json file with key 'infrastructure_info' to see
        what application is used to interact with Microsoft Azure in this
        AppScale deployment.

        Args:
          keyname: The SSH keypair name that uniquely identifies this AppScale
            deployment.
        Returns:
          A str containing the application ID used for this AppScale deployment.
        """
        return cls.get_infrastructure_option(tag="azure_app_id", keyname=keyname)

    @classmethod
    def get_app_secret_key(cls, keyname):
        """ Reads the locations.json file with key 'infrastructure_info' to get
        the secret key for the application that is used to interact with
        Microsoft Azure in this AppScale deployment.

        Args:
          keyname: The SSH keypair name that uniquely identifies this AppScale
            deployment.
        Returns:
          A str containing the secret key for the application running for this
          AppScale deployment.
        """
        return cls.get_infrastructure_option(tag="azure_app_secret_key",
                                             keyname=keyname)

    @classmethod
    def get_tenant_id(cls, keyname):
        """ Reads the locations.json file with key 'infrastructure_info' to get the
         tenant ID that is used to interact with Microsoft Azure in this
         AppScale deployment.

        Args:
          keyname: The SSH keypair name that uniquely identifies this AppScale
            deployment.
        Returns:
          A str containing the tenant ID for this account being used for this
          AppScale deployment.
        """
        return cls.get_infrastructure_option(tag="azure_tenant_id", keyname=keyname)

    @classmethod
    def get_resource_group(cls, keyname):
        """ Reads the locations.json file with key
        'infrastructure_info' to get the Azure resource group under
        which the instances are placed in this AppScale deployment.

        Args:
          keyname: The SSH keypair name that uniquely identifies this AppScale
            deployment.
        Returns:
          A str containing the resource group name being used for this
          AppScale deployment.
        """
        return cls.get_infrastructure_option(tag="azure_resource_group",
                                             keyname=keyname)

    @classmethod
    def get_storage_account(cls, keyname):
        """ Reads the locations.json file with key
        'infrastructure_info' to get the Azure storage account
        associated with the resource group in this AppScale deployment.

        Args:
          keyname: The SSH keypair name that uniquely identifies this AppScale
            deployment.
        Returns:
          A str containing the storage account name being used for this
          AppScale deployment.
        """
        return cls.get_infrastructure_option(tag="azure_storage_account",
                                             keyname=keyname)

    @classmethod
    def get_infrastructure_option(cls, tag, keyname):
        """Reads the JSON-encoded metadata on disk and returns the value for
        the key 'tag' from the dictionary retrieved using the key
        'infrastructure_info'.
        
        Args:
          keyname: A str that indicates the name of the SSH keypair that
                   uniquely identifies this AppScale deployment.
          tag: A str that indicates what we should look for in the
               infrastructure_info dictionary, this tag retrieves
               an option that was passed to AppScale at runtime.
        """
        try:
            with open(cls.locations_json_location(keyname), 'r') as file_handle:
                file_contents = yaml.safe_load(file_handle.read())
                if isinstance(file_contents, list):
                    cls.upgrade_json_file(keyname)
                    file_handle.seek(0)
                    file_contents = yaml.safe_load(file_handle.read())
                return file_contents.get('infrastructure_info', {}).get(tag)
        except IOError:
            raise BadConfigurationException("Couldn't read from locations file, "
                                            "AppScale may not be running with "
                                            "keyname {0}".format(keyname))

    @classmethod
    def upgrade_json_file(cls, keyname):
        """Upgrades the JSON file from the other version where it is a list by
        reading the JSON file, reading the YAML file, creating a dictionary in
        the "new" format and writing that to the JSON file, and then removing the
        YAML file.

        Args:
          keyname: A str that represents an SSH keypair name, uniquely identifying
            this AppScale deployment.
        Raises:
          BadConfigurationException: If there is no JSON-encoded metadata file,
            or there is no YAML-encoded metadata file, or the JSON file couldn't be
            written to.
        """
        try:
            # Open, read, and store the JSON metadata.
            role_info = ''
            with open(cls.locations_json_location(keyname), 'r') as file_handle:
                role_info = json.loads(file_handle.read())

            # If this method is running, there should be a YAML metadata file.

            yaml_locations = cls.locations_yaml_location(keyname)

            # Open, read, and store the YAML metadata.

            location_yaml_contents = ''
            with open(yaml_locations, 'r') as yaml_handle:
                locations_yaml_contents = yaml.safe_load(yaml_handle.read())

            # Create a dictionary with the information from both the YAML and JSON
            # metadata.

            locations_json = {
                'node_info': role_info,
                'infrastructure_info': locations_yaml_contents
            }

            # Write the new format to the JSON metadata file.

            with open(cls.locations_json_location(keyname), 'w') as file_handle:
                file_handle.write(json.dumps(locations_json))

            # Remove the YAML file because all information from it should be in the
            # JSON file now. At this point any failures would have raised the
            # Exception.

            if os.path.exists(yaml_locations):
                os.remove(yaml_locations)
        except IOError:
            raise BadConfigurationException("Couldn't upgrade locations json "
                                            "file, AppScale may not be running with"
                                            " keyname {0}".format(keyname))

    #
    # shell
    #
    @classmethod
    def shell(cls, command, is_verbose, num_retries=DEFAULT_NUM_RETRIES,
              stdin=None):
        """Executes a command on this machine, retrying it up to five times if
           it initially fails.
        
        Args:
          command: A str representing the command to execute.
          is_verbose: A bool that indicates if we should print the command
                      we are
        executing to stdout.
          num_retries: The number of times we should try to execute the given
                       command before aborting.
          stdin: A str that is passes as standard input to the process
        Returns:
          A str with both the standard output and standard error produced
          when the command executes.
        Raises:
          ShellException: If, after five attempts, executing the named command
          failed.
        """
        tries_left = num_retries
        try:
            while tries_left:
                logger.debug("shell> {0}".format(command))
                the_temp_file = tempfile.NamedTemporaryFile()
                if stdin is not None:
                    stdin_strio = tempfile.TemporaryFile()
                    stdin_strio.write(stdin)
                    stdin_strio.seek(0)
                    logger.debug("       stdin str: {0}"
                                           .format(stdin))
                    result = subprocess.Popen(command, shell=True, stdout=the_temp_file,
                                              stdin=stdin_strio, stderr=subprocess.STDOUT)
                else:
                    result = subprocess.Popen(command, shell=True, stdout=the_temp_file,
                                              stderr=subprocess.STDOUT)
                logger.debug("       stdout buffer: {0}"
                                       .format(the_temp_file.name))
                result.wait()
                if stdin is not None:
                    stdin_strio.close()
                if result.returncode == 0:
                    the_temp_file.seek(0)
                    output = the_temp_file.read()
                    the_temp_file.close()
                    return output
                tries_left -= 1
                if tries_left:
                    the_temp_file.close()
                    logger.debug("Command failed. Trying again momentarily."
                                           .format(command))
                else:
                    the_temp_file.seek(0)
                    output = the_temp_file.read()
                    the_temp_file.close()
                    if stdin:
                        raise ShellException("Executing command '{0} {1}' failed:\n{2}"
                                             .format(command, stdin, output))
                    else:
                        raise ShellException("Executing command '{0}' failed:\n{1}"
                                             .format(command, output))
                time.sleep(1)
        except OSError as os_error:
            if stdin:
                raise ShellException("Error executing command: '{0} {1}':{2}"
                                     .format(command, stdin, os_error))
            else:
                raise ShellException("Error executing command: '{0}':{1}"
                                     .format(command, os_error))

