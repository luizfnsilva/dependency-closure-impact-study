# Fixture A7, sabor Lua (PROTOCOLO_V_2026-10-02 §4.2): aceita o pipeline, nunca e evidencia.
# Mesmo formato do makefile do Lua: TESTS, ALL_O, alvo o, $(ALL_O): makefile.
CC= gcc
TESTS= -g -DV_TESTE
CWARNS= -Wall -DV_EXTRA=2
MYCFLAGS= $(TESTS) $(CWARNS)
CFLAGS= -O2 $(MYCFLAGS)
CORE_O= a.o b.o c.o
ALL_O= $(CORE_O)

o:	$(ALL_O)

$(ALL_O): makefile

# u.h e incluido por a.c e NAO esta declarado aqui (cabecalho nao declarado, §4.2 A7)
a.o: a.c a.h
b.o: b.c b.h
c.o: c.c c.h
