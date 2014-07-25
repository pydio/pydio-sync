#
#  Copyright 2007-2014 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
#  This file is part of Pydio.
#
#  Pydio is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Pydio is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with Pydio.  If not, see <http://www.gnu.org/licenses/>.
#
#  The latest code can be found at <http://pyd.io/>.
#

class ProcessException(Exception):
    def __init__(self, src, operation, path, detail):
        super(ProcessException, self).__init__('['+src+'] [' + operation + '] ' + path + ' ('+detail+')')
        self.src_path = path
        self.operation = operation
        self.detail = detail


class PydioSdkException(ProcessException):
    def __init__(self, operation, path, detail):
        super(PydioSdkException, self).__init__('sdk operation', operation, path, detail)

class SystemSdkException(ProcessException):
    def __init__(self, operation, path, detail):
        super(SystemSdkException, self).__init__('system operation', operation, path, detail)

class PydioSdkBasicAuthException(Exception):
    def __init__(self, type):
        super(PydioSdkBasicAuthException, self).__init__('Http-Basic authentication failed, wrong credentials?')

class PydioSdkTokenAuthException(Exception):
    def __init__(self, type):
        super(PydioSdkTokenAuthException, self).__init__('Token-based authentication failed, reload credentials?')

class PydioSdkDefaultException(Exception):
    def __init__(self, message):
        super(PydioSdkDefaultException, self).__init__(message)

class PydioSdkQuotaException(PydioSdkDefaultException):
    def __init__(self, file_name, file_size, usage, total):
        super(PydioSdkQuotaException, self).__init__('[Quota limit reached] - You are using'+' {0:.2f}'.format(float(usage)/(1024*1024))+' of'+' {0:.2f}'.format(float(total)/(1024*1024))+' Mo, '
                                                    'cannot upload '+file_name+'('+"{0:.2f}".format(float(file_size)/(1024*1024))+' Mo)')
        self.code = 507
class PydioSdkPermissionException(PydioSdkDefaultException):
    def __init__(self, message):
        super(PydioSdkDefaultException, self).__init__('[File permission] - '+message)
        self.code = 412

class InterruptException(Exception):
    def __init__(self):
        super(InterruptException, self).__init__('Stop tasks')