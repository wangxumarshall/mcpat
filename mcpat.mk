TARGET = mcpat
SHELL = /bin/sh
.PHONY: all depend clean
.SUFFIXES: .cc .o

UNAME_S := $(shell uname -s)
UNAME_M := $(shell uname -m)

ifndef NTHREADS
  NTHREADS = 4
endif

THREAD_FLAGS = -pthread
LDLIBS = -lm
CPPFLAGS = -Icacti
CXX ?= c++
CC ?= cc
ARCH_CXXFLAGS =

ifneq ($(filter x86_64 i386 i686,$(UNAME_M)),)
  ARCH_CXXFLAGS += -msse2 -mfpmath=sse
endif

ifeq ($(TAG),dbg)
  DBG = -Wall 
  OPT = -ggdb -g -O0 -DNTHREADS=1
else
  DBG = 
  OPT = -O0 -DNTHREADS=$(NTHREADS) $(ARCH_CXXFLAGS)
endif

ifneq ($(CACHE),)
  OPT += -DENABLE_MEMOIZATION
  CXXFLAGS_CACHE = -std=c++17
  LDLIBS += -llmdb
  ifeq ($(UNAME_S),Darwin)
    ifneq ($(wildcard /opt/homebrew/include/lmdb.h),)
      CPPFLAGS += -I/opt/homebrew/include
      LDFLAGS += -L/opt/homebrew/lib
    else ifneq ($(wildcard /usr/local/include/lmdb.h),)
      CPPFLAGS += -I/usr/local/include
      LDFLAGS += -L/usr/local/lib
    endif
  endif
else
  CXXFLAGS_CACHE =
endif

#CXXFLAGS = -Wall -Wno-unknown-pragmas -Winline $(DBG) $(OPT) 
CXXFLAGS = -Wno-unknown-pragmas $(DBG) $(OPT) $(CXXFLAGS_CACHE)

VPATH = cacti

SRCS  = \
  Ucache.cc \
  XML_Parse.cc \
  arbiter.cc \
  area.cc \
  array.cc \
  bank.cc \
  basic_circuit.cc \
  basic_components.cc \
  cacti_interface.cc \
  component.cc \
  core.cc \
  crossbar.cc \
  decoder.cc \
  htree2.cc \
  interconnect.cc \
  io.cc \
  iocontrollers.cc \
  logic.cc \
  main.cc \
  mat.cc \
  memoryctrl.cc \
  noc.cc \
  nuca.cc \
  parameter.cc \
  processor.cc \
  router.cc \
  results_db.cc \
  sharedcache.cc \
  subarray.cc \
  technology.cc \
  uca.cc \
  wire.cc \
  xmlParser.cc \
  powergating.cc

OBJS = $(patsubst %.cc,obj_$(TAG)/%.o,$(SRCS))

all: obj_$(TAG)/$(TARGET)
	cp -f obj_$(TAG)/$(TARGET) $(TARGET)

obj_$(TAG)/$(TARGET) : $(OBJS)
	$(CXX) $(LDFLAGS) $(OBJS) -o $@ $(CXXFLAGS) $(THREAD_FLAGS) $(LDLIBS)

#obj_$(TAG)/%.o : %.cc
#	$(CXX) -c $(CXXFLAGS) $(INCS) -o $@ $<

obj_$(TAG)/%.o : %.cc
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $(THREAD_FLAGS) -c $< -o $@

clean:
	-rm -f *.o $(TARGET)
