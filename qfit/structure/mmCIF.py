## Copyright 2002-2010 by PyMMLib Development Group (see AUTHORS file)
## This code is part of the PyMMLib distribution and governed by
## its license.  Please see the LICENSE file that should have been
## included as part of this package.
"""mmCIF file and mmCIF dictionary parser. Files are parsed into a set of data
structures where they can be further processed. The data structures can also
be constructed and written back out as mmCIF. A CIF dictionary parser is also
included as a specialized version of the mmCIF parser.
"""


import re
import copy
import itertools

##
## DATA STRUCTURES FOR HOLDING CIF INFORMATION
##
## mmCIF files are parsed into:
##         mmCIFFile -> [mmCIFData] -> [mmCIFTable] -> [mmCIFRow]
##
## mmCIF dictionaries are parsed into:
##         mmCIFDictionary -> [mmCIFData] -> [mmCIFTable] -> [mmCIFRow]
##

## mmCIF Maximum Line Length
MAX_LINE = 2048


class mmCIFError(Exception):
    """Base class of errors raised by Structure objects.
    """
    pass


class mmCIFSyntaxError(Exception):
    """Base class of errors raised by Structure objects.
    """
    def __init__(self, line_num, text):
        Exception.__init__(self)
        self.line_num = line_num
        self.text = text

    def __str__(self):
        return "[line: %d] %s" % (self.line_num, self.text)


class mmCIFRow(dict):
    """Contains one row of data. In a mmCIF file, this is one complete
    set of data found under a section. The data can be accessed by using
    the column names as class attributes.
    """
    __slots__ = ["table"]

    def __eq__(self, other):
        return id(self) == id(other)

    def __deepcopy__(self, memo):
        cif_row = mmCIFRow()
        for key, val in list(self.items()):
            cif_row[key] = val
        return cif_row

    def __contains__(self, column):
        return dict.__contains__(self, column.lower())

    def __setitem__(self, column, value):
        assert value is not None
        dict.__setitem__(self, column.lower(), value)

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __getitem__(self, column):
        return dict.__getitem__(self, column.lower())

    def getitem_lower(self, clower):
        return dict.__getitem__(self, clower)

    def __delitem__(self, column):
        dict.__delitem__(self, column.lower())

    def get(self, column, default = None):
        return dict.get(self, column.lower(), default)

    def get_lower(self, clower, default = None):
        return dict.get(self, clower, default)

    def has_key(self, column):
        return dict.has_key(self, column.lower())

    def has_key_lower(self, clower):
        return dict.has_key(self, clower)


class mmCIFTable(list):
    """Contains columns and rows of data for a mmCIF section. Rows of data
    are stored as mmCIFRow classes.
    """
    __slots__ = ["name", "columns", "columns_lower", "data"]

    def __init__(self, name, columns = None):
        assert name is not None

        list.__init__(self)
        self.name = name
        if columns is None:
            self.columns = list()
            self.columns_lower = dict()
        else:
            self.set_columns(columns)

    def __deepcopy__(self, memo):
        table = mmCIFTable(self.name, self.columns[:])
        for row in self:
            table.append(copy.deepcopy(row, memo))
        return table

    def __eq__(self, other):
        return id(self) == id(other)

    def is_single(self):
        """Return true if the table is not a _loop table with multiple
        rows of data.
        """
        return len(self) <= 1

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __getitem__(self, x):
        """Retrieves mmCIFRow at index x from the table if the argument is
        an integer. If the argument is a string, then the data from the
        first row is returned.
        """
        if isinstance(x, int):
            return list.__getitem__(self, x)

        elif isinstance(x, str):
            try:
                return self[0][x]
            except (IndexError, KeyError):
                raise KeyError

        raise TypeError(x)

    def __setitem__(self, x, value):
        assert value is not None

        if isinstance(x, int) and isinstance(value, mmCIFRow):
            value.table = self
            list.__setitem__(self, x, value)

        elif isinstance(x, str):
            try:
                self[0][x] = value
            except IndexError:
                row = mmCIFRow()
                row[x] = value
                self.append(row)

    def __delitem__(self, i):
        self.remove(self[i])

    def get(self, x, default = None):
        try:
            return self[x]
        except KeyError:
            return default

    def append(self, row):
        assert isinstance(row, mmCIFRow)
        row.table = self
        list.append(self, row)

    def insert(self, i, row):
        assert isinstance(row, mmCIFRow)
        row.table = self
        list.insert(self, i, row)

    def remove(self, row):
        assert isinstance(row, mmCIFRow)
        del row.table
        list.remove(self, row)

    def set_columns(self, columns):
        """Sets the list of column(subsection) names to the list of names in
        columns.
        """
        self.columns = list()
        self.columns_lower = dict()
        for column in columns:
            self.append_column(column)

    def append_column(self, column):
        """Appends a column(subsection) name to the table.
        """
        clower = column.lower()
        if clower in self.columns_lower:
            i = self.columns.index(self.columns_lower[clower])
            self.columns[i] = column
            self.columns_lower[clower] = column
        else:
            self.columns.append(column)
            self.columns_lower[clower] = column

    def has_column(self, column):
        """Tests if the table contains the column name.
        """
        return column.lower() in self.columns_lower

    def remove_column(self, column):
        """Removes the column name from the table.
        """
        clower = column.lower()
        if clower not in self.columns_lower:
            return
        self.columns.remove(self.columns_lower[clower])
        del self.columns_lower[clower]

    def autoset_columns(self):
        """Automatically sets the mmCIFTable column names by inspecting all
        mmCIFRow objects it contains.
        """
        clower_used = {}
        for cif_row in self:
            for clower in list(cif_row.keys()):
                clower_used[clower] = True
                if clower not in self.columns_lower:
                    self.append_column(clower)
        for clower in list(self.columns_lower.keys()):
            if clower not in clower_used:
                self.remove_column(clower)

    def get_row1(self, clower, value):
        """Return the first row which which has column data matching value.
        """
        fpred = lambda r: r.get_lower(clower) == value
        list(filter(fpred, self))
        for row in filter(fpred, self):
            return row
        return None

    def get_row(self, *args):
        """Performs a SQL-like 'AND' select aginst all the rows in the table,
        and returns the first matching row found. The arguments are a
        variable list of tuples of the form:
          (<lower-case-column-name>, <column-value>)
        For example:
          get_row(('atom_id','CA'),('entity_id', '1'))
        returns the first matching row with atom_id==1 and entity_id==1.
        """
        if len(args) == 1:
            clower, value = args[0]
            for row in self:
                if row.get_lower(clower) == value:
                    return row
        else:
            for row in self:
                match_row = True
                for clower, value in args:
                    if row.get_lower(clower) != value:
                        match_row = False
                        break
                if match_row:
                    return row
        return None

    def new_row(self):
        """Creates a new mmCIF rows, addes it to the table, and returns it.
        """
        cif_row = mmCIFRow()
        self.append(cif_row)
        return cif_row

    def iter_rows(self, *args):
        """This is the same as get_row, but it iterates over all matching
        rows in the table.
        """
        for cif_row in self:
            match_row = True
            for clower, value in args:
                if cif_row.get_lower(clower) != value:
                    match_row = False
                    break
            if match_row:
                yield cif_row

    def row_index_dict(self, clower):
        """Return a dictionary mapping the value of the row's value in
        column 'key' to the row itself. If there are multiple rows with
        the same key value, they will be overwritten with the last found
        row.
        """
        dictx = dict()
        for row in self:
            try:
                dictx[row.getitem_lower(clower)] = row
            except KeyError:
                pass
        return dictx


class mmCIFData(list):
    """Contains all information found under a data_ block in a mmCIF file.
    mmCIF files are represented differently here than their file format
    would suggest. Since a mmCIF file is more-or-less a SQL database dump,
    the files are represented here with their sections as "Tables" and
    their subsections as "Columns". The data is stored in "Rows".
    """
    __slots__ = ["name", "file"]

    def __init__(self, name):
        assert name is not None
        list.__init__(self)
        self.name = name

    def __str__(self):
        return "mmCIFData(name = %s)" % (self.name)

    def __deepcopy__(self, memo):
        data = mmCIFData(self.name)
        for table in self:
            data.append(copy.deepcopy(table, memo))
        return data

    def __eq__(self, other):
        return id(self) == id(other)

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __getitem__(self, x):
        if isinstance(x, int):
            return list.__getitem__(self, x)

        elif isinstance(x, str):
            name = x.lower()
            for ctable in self:
                if ctable.name.lower() == name:
                    return ctable
            raise KeyError(x)

        raise TypeError(x)

    def __setitem__(self, x, table):
        """
        """
        assert isinstance(table, mmCIFTable)

        try:
            old_table = self[x]
        except (KeyError, IndexError):
            pass
        else:
            self.remove(old_table)

        if isinstance(x, int):
            table.data = self
            list.__setitem__(self, x, table)

        elif isinstance(x, str):
            self.append(table)

    def __delitem__(self, x):
        """Remove a mmCIFTable by index or table name.
        """
        self.remove(self[x])

    def append(self, table):
        """Append a mmCIFTable. This will trigger the removal of any table
        with the same name.
        """
        assert isinstance(table, mmCIFTable)
        try:
            del self[table.name]
        except KeyError:
            pass
        table.data = self
        list.append(self, table)

    def insert(self, i, table):
        assert isinstance(table, mmCIFTable)
        try:
            del self[table.name]
        except KeyError:
            pass
        table.data = self
        list.insert(self, i, table)

    def remove(self, table):
        assert isinstance(table, mmCIFTable)
        del table.data
        list.remove(self, table)

    def has_key(self, x):
        try:
            self[x]
        except KeyError:
            return False
        else:
            return True

    def get(self, x, default = None):
        try:
            return self[x]
        except KeyError:
            return default

    def has_table(self, x):
        try:
            self[x]
        except KeyError:
            return False
        else:
            return True

    def get_table(self, name):
        """Looks up and returns a stored mmCIFTable class by its name. This
        name is the section key in the mmCIF file.
        """
        try:
            return self[name]
        except KeyError:
            return None
        except IndexError:
            return None

    def new_table(self, name, columns=None):
        """Creates and returns a mmCIFTable object with the given name.
        The object is added to this object before it is returned.
        """
        cif_table = mmCIFTable(name, columns)
        self.append(cif_table)
        return cif_table

    def split_tag(self, tag):
        cif_table_name, cif_column_name = tag[1:].split(".")
        return cif_table_name.lower(), cif_column_name.lower()

    def join_tag(self, cif_table_name, cif_column_name):
        return "_%s.%s" % (cif_table_name, cif_column_name)

    def get_tag(self, tag):
        """Get.
        """
        table_name, column = self.split_tag(tag)
        try:
            return self[table_name][column]
        except KeyError:
            return None

    def set_tag(self, tag, value):
        """Set.x
        """
        table_name, column = self.split_tag(tag)
        self[table_name][column] = value


class mmCIFSave(mmCIFData):
    """Class to store data from mmCIF dictionary save_ blocks. We treat
    them as non-nested sections along with data_ sections.
    This may not be correct!
    """
    pass


class mmCIFFile(list):
    """Class representing a mmCIF files.
    """
    def __deepcopy__(self, memo):
        cif_file = mmCIFFile()
        for data in self:
            cif_file.append(copy.deepcopy(data, memo))
        return cif_file

    def __str__(self):
        l = [str(cdata) for cdata in self]
        return "mmCIFFile([%s])" % (", ".join(l))

    def __eq__(self, other):
        return id(self) == id(other)

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __getitem__(self, x):
        """Retrieve a mmCIFData object by index or name.
        """
        if isinstance(x, int):
            return list.__getitem__(self, x)

        elif isinstance(x, str):
            name = x.lower()
            for cdata in self:
                if cdata.name.lower() == name:
                    return cdata
            raise KeyError(x)

        raise TypeError(x)

    def __delitem__(self, x):
        """Remove a mmCIFData by index or data name. Raises IndexError
        or KeyError if the mmCIFData object is not found, the error raised
        depends on the argument type.
        """
        self.remove(self[x])

    def append(self, cdata):
        """Append a mmCIFData object. This will trigger the removal of any
        mmCIFData object in the file with the same name.
        """
        assert isinstance(cdata, mmCIFData)
        try:
            del self[cdata.name]
        except KeyError:
            pass
        cdata.file = self
        list.append(self, cdata)

    def insert(self, i, cdata):
        assert isinstance(cdata, mmCIFData)
        try:
            del self[cdata.name]
        except KeyError:
            pass
        cdata.file = self
        list.insert(self, i, cdata)

    def has_key(self, x):
        for cdata in self:
            if cdata.name == x:
                return True
        return False

    def get(self, x, default = None):
        try:
            return self[x]
        except KeyError:
            return default

    def load_file(self, fil):
        """Load and append the mmCIF data from file object fil into self.
        The fil argument must be a file object or implement its iterface.
        """
        if isinstance(fil, str):
            fileobj = open(fil, "r")
        else:
            fileobj = fil
        mmCIFFileParser().parse_file(fileobj, self)

    def save_file(self, fil):
        if isinstance(fil, str):
            fileobj = open(fil, "w")
        else:
            fileobj = fil
        mmCIFFileWriter().write_file(fileobj, self)

    def get_data(self, name):
        """Returns the mmCIFData object with the given name. Returns None
        if no such object exists.
        """
        try:
            return self[name]
        except KeyError:
            return None
        except IndexError:
            return None

    def new_data(self, name):
        """Creates a new mmCIFData object with the given name, adds it
        to this mmCIFFile, and returns it.
        """
        cif_data = mmCIFData(name)
        self.append(cif_data)
        return cif_data


class mmCIFDictionary(mmCIFFile):
    """Class representing a mmCIF dictionary. The constructor of this class
    takes two arguments. The first is the string path for the file, or
    alternativly a file object.
    """
    pass


##
## FILE PARSERS/WRITERS
##


class mmCIFFileParser(object):
    """Stateful parser which uses the mmCIFElementFile tokenizer to read
    a mmCIF file and convert it into the mmCIFData/mmCIFTable/mmCIFRow
    data hierarchy.
    """
    def parse_file(self, fileobj, cif_file):
        self.line_number = 0
        token_iter = self.gen_token_iter(fileobj)

        try:
            self.parse(token_iter, cif_file)
        except StopIteration:
            pass
        else:
            raise mmCIFError()

    def syntax_error(self, err):
        raise mmCIFSyntaxError(self.line_number, err)

    def split_token(self, tokx):
        """Returns the mmCIF token split into a 2-tuple:
        (reserved word, name) where directive is one of the mmCIF
        reserved words: data_, loop_, global_, save_, stop_
        """
        i = tokx.find("_")
        if i == -1:
            return None, None

        rword = tokx[:i].lower()
        if rword not in ("data", "loop", "global", "save", "stop"):
            return None, None

        name = tokx[i+1:]
        return rword, name

    def parse(self, token_iter, cif_file):
        """Stateful parser for mmCIF files.

        XXX: loop_, data_, save_ tags are handled in a case-sensitive
             manor. These tokens are case-insensitive.
        """

        cif_table_cache = dict()
        cif_data = None
        cif_table = None
        cif_row = None
        state = ""

        ## ignore anything in the input file until a reserved word is
        ## found
        while True:
            tblx, colx, strx, tokx = next(token_iter)
            if tokx is None:
                continue
            rword, name = self.split_token(tokx)
            if rword is not None:
                break

        while True:
            ##
            ## PROCESS STATE CHANGES
            ##
            if tblx is not None:
                state = "RD_SINGLE"

            elif tokx is not None:
                rword, name = self.split_token(tokx)

                if rword == "loop":
                    state = "RD_LOOP"

                elif rword == "data":
                    state = "RD_DATA"

                elif rword == "save":
                    state = "RD_SAVE"

                elif rword == "stop":
                    return

                elif rword == "global":
                    self.syntax_error("unable to handle global_ syntax")

                else:
                    self.syntax_error("bad token #1: " + str(tokx))

            else:
                self.syntax_error("bad token #2")
                return

            ##
            ## PROCESS DATA IN RD_SINGLE STATE
            ##
            if state == "RD_SINGLE":
                try:
                    cif_table = cif_table_cache[tblx]
                except KeyError:
                    cif_table = cif_table_cache[tblx] = mmCIFTable(tblx)

                    try:
                        cif_data.append(cif_table)
                    except AttributeError:
                        self.syntax_error("section not contained in data_ block")
                        return

                    cif_row = mmCIFRow()
                    cif_table.append(cif_row)
                else:
                    try:
                        cif_row = cif_table[0]
                    except IndexError:
                        self.syntax_error("bad token #3")
                        return

                ## check for duplicate entries
                if colx in cif_table.columns:
                    self.syntax_error("redefined subsection (column)")
                    return
                else:
                    cif_table.append_column(colx)

                ## get the next token from the file, it should be the data
                ## keyed by the previous token
                tx, cx, strx, tokx = next(token_iter)
                if tx is not None or (strx is None and tokx is None):
                    self.syntax_error("missing data for _%s.%s" % (tblx,colx))

                if tokx is not None:
                    ## check token for reserved words
                    rword, name = self.split_token(tokx)
                    if rword is not None:
                        if rword == "stop":
                            return
                        self.syntax_error("unexpected reserved word: %s" % (rword))

                    if tokx != ".":
                        cif_row[colx] = tokx

                elif strx is not None:
                    cif_row[colx] = strx

                else:
                    self.syntax_error("bad token #4")

                tblx, colx, strx, tokx = next(token_iter)
                continue

            ###
            ## PROCESS DATA IN RD_LOOP STATE
            ##
            ## This is entered upon the beginning of a loop, and
            ## the loop is read completely before exiting.
            ###
            elif state == "RD_LOOP":
                ## the first section.subsection (tblx.colx) is read
                ## to create the section(table) name for the entire loop
                tblx, colx, strx, tokx = next(token_iter)

                if tblx is None or colx is None:
                    self.syntax_error("bad token #5")
                    return

                if tblx in cif_table_cache:
                    self.syntax_error("_loop section duplication")
                    return

                cif_table = mmCIFTable(tblx)

                try:
                    cif_data.append(cif_table)
                except AttributeError:
                    self.syntax_error("_loop section not contained in data_ block")
                    return

                cif_table.append_column(colx)

                ## read the remaining subsection definitions for the loop_
                while True:
                    tblx, colx, strx, tokx = next(token_iter)

                    if tblx is None:
                        break

                    if tblx != cif_table.name:
                        self.syntax_error("changed section names in loop_")
                        return

                    cif_table.append_column(colx)

                ## before starting to read data, check tokx for any control
                ## tokens
                if tokx is not None:
                    rword, name = self.split_token(tokx)
                    if rword is not None:
                        if rword == "stop":
                            return
                        else:
                            self.syntax_error(
                                "unexpected reserved word: %s" % (rword))

                ## now read all the data
                while True:
                    cif_row = mmCIFRow()
                    cif_table.append(cif_row)

                    for col in cif_table.columns:
                        if tokx is not None:
                            if tokx != ".":
                                cif_row[col] = tokx
                        elif strx is not None:
                            cif_row[col] = strx

                        tblx,colx,strx,tokx = next(token_iter)

                    ## the loop ends when one of these conditions is met:
                    ## condition #1: a new table is encountered
                    if tblx is not None:
                        break

                    ## condition #2: a reserved word is encountered
                    if tokx is not None:
                        rword, name = self.split_token(tokx)
                        if rword is not None:
                            break

                continue

            elif state == "RD_DATA":
                cif_data = mmCIFData(tokx[5:])
                cif_file.append(cif_data)
                cif_table_cache = dict()
                cif_table = None

                tblx,colx,strx,tokx = next(token_iter)

            elif state == "RD_SAVE":
                cif_data = mmCIFSave(tokx[5:])
                cif_file.append(cif_data)
                cif_table_cache = dict()
                cif_table = None

                tblx,colx,strx,tokx = next(token_iter)


    def gen_token_iter(self, fileobj):
        re_tok = re.compile(
            r"(?:"

             "(?:_(.+?)[.](\S+))"               "|"  # _section.subsection

             "(?:['\"](.*?)(?:['\"]\s|['\"]$))" "|"  # quoted strings

             "(?:\s*#.*$)"                      "|"  # comments

             "(\S+)"                                 # unquoted tokens

             ")")

        file_iter = iter(fileobj)

        ## parse file, yielding tokens for self.parser()
        while True:
            ln = next(file_iter)
            self.line_number += 1

            ## skip comments
            if ln.startswith("#"):
                continue

            ## semi-colen multi-line strings
            if ln.startswith(";"):
                lmerge = [ln[1:]]
                while True:
                    ln = next(file_iter)
                    self.line_number += 1
                    if ln.startswith(";"):
                        break
                    lmerge.append(ln)

                lmerge[-1] = lmerge[-1].rstrip()
                yield (None, None, "".join(lmerge), None)
                continue

            ## split line into tokens
            tok_iter = re_tok.finditer(ln)

            for tokm in tok_iter:
                groups = tokm.groups()
                if groups != (None, None, None, None):
                    yield groups


class mmCIFFileWriter(object):
    """Writes out a mmCIF file using the data in the mmCIFData list.
    """
    def write_file(self, fil, cif_data_list):
        self.fil = fil

        ## constant controlls the spacing between columns
        self.SPACING = 2

        ## iterate through the data sections and write them
        ## out to the file
        for cif_data in cif_data_list:
            self.cif_data = cif_data
            self.write_cif_data()

    def write(self, x):
        self.fil.write(x)

    def writeln(self, x = ""):
        self.fil.write(x + "\n")

    def write_mstring(self, mstring):
        self.write(self.form_mstring(mstring))

    def form_mstring(self, mstring):
        l = [";"]

        lw = MAX_LINE - 2
        for x in mstring.split("\n"):
            if x == "":
                l.append("\n")
                continue

            while len(x) > 0:
                l.append(x[:lw])
                l.append("\n")

                x  = x[lw:]

        l.append(";\n")
        return "".join(l)

    def data_type(self, x):
        """Analyze x and return its type: token, qstring, mstring
        """
        assert x is not None

        if not isinstance(x, str):
            x = str(x)
            return x, "token"

        if x == "" or x == ".":
            return ".", "token"

        if x.find("\n") != -1:
            return x, "mstring"

        if x.count(" ") != 0 or x.count("\t") != 0 or x.count("#") != 0:
            if len(x) > (MAX_LINE - 2):
                return x, "mstring"
            if x.count("' ") != 0 or x.count('" ') != 0:
                return x, "mstring"
            return x, "qstring"

        if len(x) < MAX_LINE:
            return x, "token"
        else:
            return x, "mstring"

    def write_cif_data(self):
        if isinstance(self.cif_data, mmCIFSave):
            self.writeln("save_%s" % self.cif_data.name)
        else:
            self.writeln("data_%s" % self.cif_data.name)

        self.writeln("#")

        for cif_table in self.cif_data:
            ## ignore tables without data rows
            if len(cif_table) == 0:
                continue

            ## special handling for tables with one row of data
            elif len(cif_table) == 1:
                self.write_one_row_table(cif_table)

            ## _loop tables
            elif len(cif_table) > 1 and len(cif_table.columns) > 0:
                self.write_multi_row_table(cif_table)

            else:
                raise mmCIFError()

            self.writeln("#")

    def write_one_row_table(self, cif_table):
        row = cif_table[0]

        ## determine max key length for formatting output
        kmax  = 0
        table_len = len(cif_table.name) + 2
        for col in cif_table.columns:
            klen = table_len + len(col)
            assert klen < MAX_LINE
            kmax = max(kmax, klen)

        ## we need a space after the tag
        kmax += self.SPACING
        vmax  = MAX_LINE - kmax - 1

        ## write out the keys and values
        for col in cif_table.columns:

            cif_key = "_%s.%s" % (cif_table.name, col)
            l = [cif_key.ljust(kmax)]

            try:
                x0 = row[col]
            except KeyError:
                x = "?"
                dtype = "token"
            else:
                x, dtype = self.data_type(x0)

            if dtype == "token":
                if len(x) > vmax:
                    l.append("\n")
                l.append("%s\n" % (x))
                self.write("".join(l))

            elif dtype == "qstring":
                if len(x) > vmax:
                    l.append("\n")
                    self.write("".join(l))
                    self.write_mstring(x)

                else:
                    l.append("'%s'\n" % (x))
                    self.write("".join(l))

            elif dtype == "mstring":
                l.append("\n")
                self.write("".join(l))
                self.write_mstring(x)

    def write_multi_row_table(self, cif_table):
        ## write the key description for the loop_
        self.writeln("loop_")
        for col in cif_table.columns:
            key = "_%s.%s" % (cif_table.name, col)
            assert len(key) < MAX_LINE
            self.writeln(key)

        col_len_map   = {}
        col_dtype_map = {}

        for row in cif_table:
            for col in cif_table.columns:
                ## get data and data type
                try:
                    x0 = row[col]
                except KeyError:
                    lenx  = 1
                    dtype = "token"
                else:
                    x, dtype = self.data_type(x0)

                    ## determine write length of data
                    if dtype == "token":
                        lenx = len(x)
                    elif dtype == "qstring":
                        lenx = len(x) + 2
                    else:
                        lenx = 0

                try:
                    col_dtype = col_dtype_map[col]
                except KeyError:
                    col_dtype_map[col] = dtype
                    col_len_map[col]   = lenx
                    continue

                ## update the column charactor width if necessary
                if col_len_map[col] < lenx:
                    col_len_map[col] = lenx

                ## modify column data type if necessary
                if col_dtype != dtype:
                    if dtype == "mstring":
                        col_dtype_map[col] = "mstring"
                    elif col_dtype == "token" and dtype == "qstring":
                        col_dtype_map[col] = "qstring"

        ## form a write list of the column names with values of None to
        ## indicate a newline
        wlist = []
        llen = 0
        for col in cif_table.columns:
            dtype = col_dtype_map[col]

            if dtype == "mstring":
                llen = 0
                wlist.append((None, None, None))
                wlist.append((col, dtype, None))
                continue

            lenx  = col_len_map[col]
            if llen == 0:
                llen = lenx
            else:
                llen += self.SPACING + lenx

            if llen > (MAX_LINE - 1):
                wlist.append((None, None, None))
                llen = lenx

            wlist.append((col, dtype, lenx))

        ## write out the data
        spacing   = " " * self.SPACING
        add_space = False
        listx     = []

        for row in cif_table:
            for (col, dtype, lenx) in wlist:

                if col is None:
                    add_space = False
                    listx.append("\n")
                    continue

                if add_space == True:
                    add_space = False
                    listx.append(spacing)

                if dtype == "token":
                    x = str(row.get(col, "."))
                    if x == "":
                        x = "."
                    x = x.ljust(lenx)
                    listx.append(x)
                    add_space = True

                elif dtype == "qstring":
                    x = row.get(col, ".")
                    if x == "":
                        x = "."
                    elif x != "." and x != "?":
                        x = "'%s'" % (x)
                    x = x.ljust(lenx)
                    listx.append(x)
                    add_space = True

                elif dtype == "mstring":
                    try:
                        listx.append(self.form_mstring(row[col]))
                    except KeyError:
                        listx.append(".\n")
                    add_space = False

            add_space = False
            listx.append("\n")

            ## write out strx if it gets big to avoid using a lot of
            ## memory
            if len(listx) > 1024:
                self.write("".join(listx))
                listx = []

        ## write out the _loop section
        self.write("".join(listx))


### <testing>
def test_module():
    import sys
    try:
        path = sys.argv[1]
    except IndexError:
        print("usage: mmCIF.py <mmCIF file path>")
        raise SystemExit

    cif = mmCIFDictionary()
    cif.load_file(path)
    cif.save_file(sys.stdout)

if __name__ == '__main__':
    test_module()
### </testing>
