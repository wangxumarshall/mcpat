#pragma once

#ifdef ENABLE_MEMOIZATION

#include <filesystem>
#include <istream>
#include <lmdb.h>
#include <ostream>
#include <vector>

#include "cacti_interface.h"

class ResultsDB
{
  public:
    static ResultsDB& getInstance();

    ResultsDB(const ResultsDB&) = delete;
    ResultsDB& operator=(const ResultsDB&) = delete;

    bool get(const InputParameter& input_parameter_key, uca_org_t& uca_org_val);
    void put(const InputParameter& input_parameter_key, const uca_org_t& uca_org_val);

  private:
    ResultsDB();
    ~ResultsDB();

    bool openDatabase();
    void closeDatabase();
    std::filesystem::path createTmpPath() const;

    template <typename T>
    static void writeScalar(std::ostream& os, const T& value);

    template <typename T>
    static void readScalar(std::istream& is, T& value);

    template <typename T>
    static void writePointer(std::ostream& os, const T* value);

    template <typename T>
    static void readPointer(std::istream& is, T*& value);

    static void writeVector(std::ostream& os, const std::vector<double>& values);
    static void readVector(std::istream& is, std::vector<double>& values);

    static void serialize(std::ostream& os, const InputParameter& param);
    static void deserialize(std::istream& is, InputParameter& param);
    static void serialize(std::ostream& os, const uca_org_t& param);
    static void deserialize(std::istream& is, uca_org_t& param);
    static void serialize(std::ostream& os, const mem_array& param);
    static void deserialize(std::istream& is, mem_array& param);
    static void serialize(std::ostream& os, const min_values_t& param);
    static void deserialize(std::istream& is, min_values_t& param);

    std::filesystem::path database_path_;
    MDB_env* env_;
    MDB_dbi dbi_;
    bool ready_;
};

#endif
