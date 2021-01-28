def get_table_descriptions():
    '''
    '''
    descriptions = {

        '_user': '''
            name varchar(50) not null primary key,
            passwd varchar(20),
            role varchar(10) not null,
            access varchar(50) not null
            ''',

        '_empty_table': '''
            name varchar(50) not null primary key
            ''',

        '_problem_info': '''
            name varchar(50) not null primary key,
            problem_name varchar(50) not null
            ''',

        '_config': '''
            id int auto_increment primary key,
            name varchar(50) not null,
            config text not null
            ''',

        '_lock': '''
            name varchar(50) not null,
            rowid int not null
            ''',
    }

    return descriptions


def get_table_post_processes():
    '''
    '''
    post_processes = {

        '_lock': '''
            alter table _lock add unique index(name, rowid)
            ''',
    }
    
    return post_processes