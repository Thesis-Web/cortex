#include "sqlite3.h"
#include <stdio.h>
int main(){ sqlite3 *db; sqlite3_open(":memory:", &db); printf("linked sqlite %s\n", sqlite3_libversion()); sqlite3_close(db); return 0; }
