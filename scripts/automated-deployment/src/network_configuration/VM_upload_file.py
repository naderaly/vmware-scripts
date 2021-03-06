#!/usr/bin/env python
from __future__ import with_statement
import atexit
import requests
from ..tools import cli
from ..tools import tasks
from pyVim import connect
from pyVmomi import vim, vmodl
import re
import os
import sys

from .get_vm_info import GetVMInfo
from k8_vmware.vsphere.Sdk import Sdk
from ...config import Config


def get_args():
    """Get command line args from the user.
    """

    parser = cli.build_arg_parser()

    parser.add_argument('-v', '--vm_uuid',
                        required=False,
                        action='store',
                        help='Virtual machine uuid')

    parser.add_argument('-r', '--vm_user',
                        required=False,
                        action='store',
                        help='virtual machine user name')

    parser.add_argument('-w', '--vm_pwd',
                        required=False,
                        action='store',
                        help='virtual machine password')

    parser.add_argument('-l', '--path_inside_vm',
                        required=False,
                        action='store',
                        help='Path inside VM for upload')

    parser.add_argument('-f', '--upload_file',
                        required=False,
                        action='store',
                        help='Path of the file to be uploaded from host')

    args = parser.parse_args()

    cli.prompt_for_password(args)
    return args


class VMUploadFile:

    def __init__(self):

        self.args = get_args()
        
        self.sdk = Sdk()

        self.__config = Config()

        # path of file to upload
        self.host_file_path = os.path.dirname(os.path.realpath(__file__))

        # inside vm path to upload to
        self.vm_path = self.__config.UPLOAD_PATH_INSIDE_VM

        try:
            self.service_instance = connect.SmartConnectNoSSL( host=self.__config.VSPHERE_HOST,
                                                               user=self.__config.VSPHERE_USERNAME,
                                                               pwd=self.__config.VSPHERE_PASSWORD,
                                                               port=self.__config.PORT)

            atexit.register(connect.Disconnect, self.service_instance)
            print("connected successfully to esxi server %s!" % self.__config.VSPHERE_HOST)
        
        except Exception as e:     
            print("Unable to connect to %s" % self.__config.VSPHERE_HOST)
            raise e

    def get_bios_uuid(self):
        vm_info_data = GetVMInfo(si=self.service_instance).main()
        print(vm_info_data)
        bios_uuid = vm_info_data.get("bios_uuid")
        return bios_uuid

    def main(self):
        """
        Simple command-line program for Uploading a file from host to guest
        """
        bios_uuid = self.get_bios_uuid()
        print("Instance UUID: %s" % bios_uuid)
        
        upload_file = os.path.join(self.host_file_path, self.__config.UPLOAD_FILE_NAME)
        print(upload_file)

        try:
            
            content = self.service_instance.RetrieveContent()

            # vm = content.searchIndex.FindByUuid(None, args.vm_uuid, True)
            # vm = content.searchIndex.FindByUuid(datacenter=None,
            #                                     uuid=bios_uuid,
            #                                     vmSearch=True,
            #                                     instanceUuid=True)
            
            try:
                vm = self.sdk.find_by_uuid(bios_uuid).vm
                print(vm)
            except Exception as e:
                print("Cannot find the VM, got error: %s" % e)
                sys.exit(1)

            print("vm2:", vm)
            
            creds = vim.vm.guest.NamePasswordAuthentication(
                username=self.__config.VM_USERNAME, password=self.__config.VM_PASSWORD)
            with open(upload_file, 'rb') as myfile:
                print("myfile:", myfile, upload_file)
                fileinmemory = myfile.read()
            print("fileinmemory:", fileinmemory)

            try:
                file_attribute = vim.vm.guest.FileManager.FileAttributes()
                print("file attribute:", file_attribute)
                url = content.guestOperationsManager.fileManager. \
                    InitiateFileTransferToGuest(vm, creds, self.vm_path,
                                                file_attribute,
                                                len(fileinmemory), 
                                                True)
                # When : host argument becomes https://*:443/guestFile?
                # Ref: https://github.com/vmware/pyvmomi/blob/master/docs/ \
                #            vim/vm/guest/FileManager.rst
                # Script fails in that case, saying URL has an invalid label.
                # By having hostname in place will take take care of this.
                url = re.sub(r"^https://\*:", "https://"+str(self.__config.VSPHERE_HOST)+":", url)
                resp = requests.put(url, data=fileinmemory, verify=False)
                if not resp.status_code == 200:
                    print("Error while uploading file")
                else:
                    print("Successfully uploaded file")
            except IOErrorn as e:
                print(e)
        except vmodl.MethodFault as error:
            print("Caught vmodl fault : " + error.msg)
            return -1

        return 0

# Start program
if __name__ == "__main__":
    VMUploadFile().main()