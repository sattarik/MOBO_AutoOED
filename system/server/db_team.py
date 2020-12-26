import os
import mysql.connector
import requests
import ipaddress
import numpy as np


class Database:
    '''
    '''
    def __init__(self, host, user, passwd):
        '''
        '''
        self.login_info = {
            'host': host,
            'user': user,
            'passwd': passwd,
        }
        self.database = 'openmobo'

        # connect mysql
        self.conn = mysql.connector.connect(**self.login_info, autocommit=True)
        self.cursor = self.conn.cursor()

        # connect database
        if self.check_db_exist(self.database):
            self.execute(f'use {self.database}')
        else:
            self.execute(f'create database {self.database}')
            self.execute(f'use {self.database}')
            
        if user == 'root':
            if not self.check_table_exist('user'):
                self.create_table(name='user', description='\
                    name varchar(20) not null primary key,\
                    passwd varchar(20),\
                    role varchar(10) not null,\
                    access varchar(20) not null')

            if not self.check_table_exist('empty_table'):
                self.create_table(name='empty_table', description='name varchar(20) not null')

            self.create_function_login_verify()
            self.create_procedure_init_table()

        self.reserved_tables = ['user', 'empty_table']

    def connect(self, force=False):
        '''
        '''
        if self.conn.is_connected() and not force: return
        self.conn = mysql.connector.connect(**self.login_info, autocommit=True)
        self.cursor = self.conn.cursor()
        self.execute(f'use {self.database}')
        
    def check_root(self):
        '''
        '''
        assert self.login_info['user'] == 'root', 'root previlege is needed'

    def check_function_exist(self, name):
        '''
        '''
        query = f'''
            select exists(select * from information_schema.routines where routine_type='function' and routine_schema='{self.database}' and routine_name='{name}');
            '''
        self.execute(query)
        return self.fetchone()[0]

    def check_procedure_exist(self, name):
        '''
        '''
        query = f'''
            select exists(select * from information_schema.routines where routine_type='procedure' and routine_schema='{self.database}' and routine_name='{name}');
            '''
        self.execute(query)
        return self.fetchone()[0]

    def create_function_login_verify(self):
        '''
        ROOT
        '''
        self.check_root()
        if self.check_function_exist('login_verify'): return
        query = f'''
            create function login_verify( 
                name_ varchar(20), role_ varchar(10), access_ varchar(20)
            )
            returns boolean
            begin
                declare user_exist, init_table_exist, uninit_table_exist boolean;
                select exists(select * from user where name=name_ and role=role_ and (access=access_ or access='*')) into user_exist;
                select exists(select * from information_schema.tables where table_schema='{self.database}' and table_name=access_) into init_table_exist;
                select exists(select * from empty_table where name=access_) into uninit_table_exist;
                return user_exist and (init_table_exist or uninit_table_exist);
            end
            '''
        self.execute(query)

    def login_verify(self, name, role, access):
        '''
        '''
        query = f'''
            select login_verify('{name}', '{role}', '{access}')
            '''
        self.execute(query)
        return self.fetchone()[0]

    def create_procedure_init_table(self):
        '''
        ROOT
        '''
        self.check_root()
        if self.check_procedure_exist('init_table'): return
        query = f'''
            create procedure init_table( 
                in name_ varchar(20), in description_ varchar(10000)
            )
            begin
                set @query = concat('create table ', name_, '(', description_, ')');
                prepare stmt from @query;
                execute stmt;
                delete from empty_table where name=name_;
            end
            '''
        self.execute(query)

    def init_table(self, name, description):
        '''
        '''
        query = f'''
            call init_table('{name}', "{description}")
            '''
        self.execute(query)

    def check_db_exist(self, name):
        '''
        '''
        self.execute(f"show databases like '{name}'")
        return self.cursor.fetchone() != None

    def get_user_list(self, role=None):
        '''
        ROOT
        '''
        self.check_root()
        if role is None:
            self.execute('select name from user')
        else:
            self.execute(f"select name from user where role = '{role}'")
        user_list = [res[0] for res in self.cursor]
        return user_list

    def get_active_user_list(self, return_host=False, role=None):
        '''
        ROOT
        '''
        self.check_root()
        user_list = self.get_user_list(role=role)
        active_user_list = []
        active_host_list = []
        self.execute(f"select user, host from information_schema.processlist where db = '{self.database}'")
        for res in self.cursor:
            user, host = res
            if user in user_list:
                active_user_list.append(user)
                active_host_list.append(host)
        if return_host:
            return active_user_list, active_host_list
        else:
            return active_user_list
    
    def get_current_user(self, return_host=False):
        '''
        '''
        user = self.login_info['user']
        if not return_host:
            return user
        host = self.login_info['host']
        if host == 'localhost' or ipaddress.ip_address(host).is_private:
            try:
                host = requests.get('https://checkip.amazonaws.com').text.strip()
            except:
                raise Exception('Cannot identify public IP address, please check internet connection')
        return user, host

    def check_user_exist(self, name):
        '''
        '''
        self.check_root()
        user_list = self.get_user_list()
        return name in user_list

    def create_user(self, name, passwd, role, access):
        '''
        ROOT
        '''
        self.check_root()
        assert not self.check_user_exist(name), f'user {name} already exists'

        # create user
        try:
            self.execute(f'drop user {name}')
            self.execute('flush privileges')
        except:
            pass
        self.execute(f"create user '{name}'@'%' identified by '{passwd}'")

        # grant table access
        table_list = self.get_table_list()
        if access == '*':
            for table in table_list:
                self.execute(f"grant all privileges on {self.database}.{table} to '{name}'@'%'")
        elif access == '':
            pass
        else:
            assert access in table_list, f"table {access} doesn't exist "
            self.execute(f"grant all privileges on {self.database}.{access} to '{name}'@'%'")

        # grant function & procedure access
        self.execute(f"grant execute on function {self.database}.login_verify to '{name}'@'%'")
        if role == 'Scientist':
            self.execute(f"grant execute on procedure {self.database}.init_table to '{name}'@'%'")

        self.execute('flush privileges')

        self.insert_data(table='user', column=None, data=(name, passwd, role, access))

    def update_user(self, name, passwd, role, access):
        '''
        ROOT
        '''
        self.check_root()
        assert self.check_user_exist(name), f"user {name} doesn't exist"

        self.execute(f"select name, passwd, role, access from user where name = '{name}'")
        user_info = self.cursor.fetchone()
        if user_info == (name, passwd, role, access): return
        _, old_passwd, _, old_access = user_info

        if old_passwd != passwd:
            self.execute(f"alter user '{name}'@'%' identified by '{passwd}'")

        if old_access != access:
            table_list = self.get_table_list()
            if access == '*':
                for table in table_list:
                    self.execute(f"grant all privileges on {self.database}.{table} to '{name}'@'%'")
            else:
                if old_access == '*':
                    for table in table_list:
                        self.execute(f"revoke all privileges on {self.database}.{table} from '{name}'@'%'")
                elif old_access == '':
                    pass
                else:
                    self.execute(f"revoke all privileges on {self.database}.{old_access} from '{name}'@'%'")
                self.execute(f"grant all privileges on {self.database}.{access} to '{name}'@'%'")
            self.execute('flush privileges')

        self.update_data(table='user', column=('passwd', 'role', 'access'), data=(passwd, role, access), condition=f"name = '{name}'")

    def remove_user(self, name):
        '''
        ROOT
        '''
        self.check_root()
        user_list = self.get_user_list()
        assert name in user_list, f"user {name} doesn't exist"
        assert name != 'root', 'cannot drop root user'

        self.execute(f'drop user {name}')
        self.execute('flush privileges')

        self.delete_data(table='user', condition=f"name = '{name}'")

    def get_table_list(self):
        '''
        '''
        self.execute('show tables')
        table_list = [res[0] for res in self.cursor if res[0] not in self.reserved_tables]
        return table_list

    def check_table_exist(self, name):
        '''
        '''
        self.execute('show tables')
        table_list = [res[0] for res in self.cursor]
        return name in table_list

    def load_table(self, name):
        '''
        '''
        if not (self.check_table_exist(name) or self.check_empty_table_exist(name)):
            raise Exception(f"Table {name} doesn't exist")
        assert name != 'user', 'cannot load user table'

        if self.check_table_exist(name):
            self.execute(f'select * from {name}')
            return self.cursor.fetchall()
        else:
            return None

    def create_table(self, name, description):
        '''
        ROOT
        '''
        self.check_root()
        if self.check_table_exist(name):
            raise Exception(f'Table {name} exists')
        self.execute(f'create table {name} ({description})')

    def import_table_from_file(self, name, file_path):
        '''
        '''
        # TODO
        raise NotImplementedError
        # self.check_root()
        # if not os.path.exists(file_path):
        #     raise Exception(f'Table file {file_path} does not exist')
        # self.create_table(name)

    def remove_table(self, name):
        '''
        ROOT
        '''
        self.check_root()
        if not self.check_table_exist(name):
            raise Exception(f'Table {name} does not exist')
        self.execute(f'drop table {name}')
        self.execute(f"update user set access='' where access='{name}'")

    def get_empty_table_list(self):
        '''
        ROOT
        '''
        self.check_root()
        self.execute('select name from empty_table')
        table_list = [res[0] for res in self.cursor]
        return table_list

    def get_all_table_list(self):
        '''
        ROOT
        '''
        self.check_root()
        return self.get_table_list() + self.get_empty_table_list()

    def check_empty_table_exist(self, name):
        '''
        ROOT
        '''
        self.check_root()
        return name in self.get_empty_table_list()

    def create_empty_table(self, name):
        '''
        ROOT
        '''
        self.check_root()
        if self.check_table_exist(name) or self.check_empty_table_exist(name):
            raise Exception(f'Table {name} exists')
        self.insert_data(table='empty_table', column=None, data=[name])

    def remove_empty_table(self, name):
        '''
        ROOT
        '''
        self.check_root()
        if not self.check_empty_table_exist(name):
            raise Exception(f'Table {name} does not exist')
        self.delete_data(table='empty_table', condition=f"name = '{name}'")

    def insert_data(self, table, column, data, transform=False):
        '''
        '''
        if transform:
            data = self.transform_data(data)
        if type(data) == np.ndarray:
            data = data.tolist()
        if column is None:
            query = f"insert into {table} values ({','.join(['%s'] * len(data))})"
        elif type(column) == str:
            query = f"insert into {table} values (%s)"
        else:
            # assert len(column) == len(data), 'length mismatch of keys and values'
            query = f"insert into {table} ({','.join(column)}) values ({','.join(['%s'] * len(data))})"
        self.execute(query, data)

    def insert_multiple_data(self, table, column, data, transform=False):
        '''
        '''
        if transform:
            data = self.transform_multiple_data(data)
        if type(data) == np.ndarray:
            data = data.tolist()
        if column is None:
            query = f"insert into {table} values ({','.join(['%s'] * len(data[0]))})"
        elif type(column) == str:
            query = f"insert into {table} values (%s)"
        else:
            # assert len(column) == len(data[0]), 'length mismatch of keys and values'
            query = f"insert into {table} ({','.join(column)}) values ({','.join(['%s'] * len(data[0]))})"
        self.executemany(query, data)

    def update_data(self, table, column, data, condition, transform=False):
        '''
        '''
        if transform:
            data = self.transform_data(data)
        if type(data) == np.ndarray:
            data = data.tolist()
        if type(column) == str:
            query = f"update {table} set {column}=%s where {condition}"
        else:
            # assert len(column) == len(data), 'length mismatch of keys and values'
            query = f"update {table} set {','.join([col + '=%s' for col in column])} where {condition}"
        self.execute(query, data)

    def update_multiple_data(self, table, column, data, condition, transform=False):
        '''
        '''
        if transform:
            data = self.transform_multiple_data(data)
        if type(data) == np.ndarray:
            data = data.tolist()
        if type(column) == str:
            query = f"update {table} set {column}=%s where {condition}"
        else:
            # assert len(column) == len(data[0]), 'length mismatch of keys and values'
            query = f"update {table} set {','.join([col + '=%s' for col in column])} where {condition}"
        self.executemany(query, data)

    def delete_data(self, table, condition):
        '''
        '''
        self.execute(f'delete from {table} where {condition}')
    
    def transform_data(self, data_list):
        '''
        '''
        new_data_list = []
        for data in data_list:
            data = np.array(data, dtype=str)
            if len(data.shape) == 0:
                data = np.expand_dims(data, axis=0)
            assert len(data.shape) == 1, f'error: data shape {data.shape}'
            new_data_list.append(data)
        return np.hstack(new_data_list)

    def transform_multiple_data(self, data_list):
        '''
        '''
        new_data_list = []
        for data in data_list:
            data = np.array(data, dtype=str)
            if len(data.shape) == 1:
                data = np.expand_dims(data, axis=1)
            assert len(data.shape) == 2
            new_data_list.append(data)
        return np.hstack(new_data_list)

    def select_data(self, table, column, condition=None):
        '''
        '''
        if column is None:
            query = f'select * from {table}'
        elif type(column) == str:
            query = f"select {column} from {table}"
        else:
            query = f"select {','.join(column)} from {table}"
        if condition is not None:
            query += f' where {condition}'
        self.execute(query)
        return self.fetchall()

    def select_first_data(self, table, column, condition=None):
        '''
        '''
        if column is None:
            query = f'select * from {table}'
        elif type(column) == str:
            query = f"select {column} from {table}"
        else:
            query = f"select {','.join(column)} from {table}"
        if condition is not None:
            query += f' where {condition}'
        self.execute(query)
        return self.fetchone()
    
    def select_last_data(self, table, column, condition=None):
        '''
        '''
        if column is None:
            query = f'select * from {table} order by id desc limit 1'
        elif type(column) == str:
            query = f"select {column} from {table} order by id desc limit 1"
        else:
            query = f"select {','.join(column)} from {table} order by id desc limit 1"
        if condition is not None:
            query += f' where {condition}'
        self.execute(query)
        return self.fetchone()

    def get_column_names(self, table):
        '''
        '''
        query = f"select column_name from information_schema.columns where table_name = '{table}'"
        self.execute(query)
        column_names = [res[0] for res in self.cursor]
        return column_names

    # def _execute(self, func, query, data):
    #     '''
    #     '''
    #     self.connect() # TODO: check latency
    #     done = False
    #     curr_try, max_try = 0, 3
    #     while not done and curr_try <= max_try:
    #         try:
    #             if data is None:
    #                 func(query)
    #             else:
    #                 func(query, data)
    #             done = True
    #         except Exception as e:
    #             done = False
    #             curr_try += 1
    #             if curr_try < max_try:
    #                 print(f'Database execution error "{e}"", retrying {curr_try} times')
    #     if curr_try > max_try:
    #         print(f'Database execution error, exceeded max number of retry')

    def execute(self, query, data=None):
        '''
        '''
        self.connect() # TODO: check latency
        # TODO: exception handling
        if data is None:
            self.cursor.execute(query)
        else:
            self.cursor.execute(query, data)

    def executemany(self, query, data=None):
        '''
        '''
        self.connect() # TODO: check latency
        # TODO: exception handling
        if data is None:
            self.cursor.executemany(query)
        else:
            self.cursor.executemany(query, data)

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    def get_checksum(self, table):
        '''
        '''
        self.execute(f'checksum table {table}')
        return self.cursor.fetchone()[1]

    def quit(self):
        '''
        '''
        self.conn.disconnect()