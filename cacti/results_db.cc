#ifdef ENABLE_MEMOIZATION

#include "results_db.h"

#include <cstddef>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <sstream>
#include <string>

#include "Ucache.h"

#define MCPAT_INPUT_PARAMETER_FIELDS(APPLY) \
  APPLY(cache_sz) \
  APPLY(line_sz) \
  APPLY(assoc) \
  APPLY(nbanks) \
  APPLY(out_w) \
  APPLY(specific_tag) \
  APPLY(tag_w) \
  APPLY(access_mode) \
  APPLY(obj_func_dyn_energy) \
  APPLY(obj_func_dyn_power) \
  APPLY(obj_func_leak_power) \
  APPLY(obj_func_cycle_t) \
  APPLY(F_sz_nm) \
  APPLY(F_sz_um) \
  APPLY(specific_hp_vdd) \
  APPLY(hp_Vdd) \
  APPLY(specific_lstp_vdd) \
  APPLY(lstp_Vdd) \
  APPLY(specific_lop_vdd) \
  APPLY(lop_Vdd) \
  APPLY(specific_vcc_min) \
  APPLY(user_defined_vcc_min) \
  APPLY(user_defined_vcc_underflow) \
  APPLY(num_rw_ports) \
  APPLY(num_rd_ports) \
  APPLY(num_wr_ports) \
  APPLY(num_se_rd_ports) \
  APPLY(num_search_ports) \
  APPLY(is_main_mem) \
  APPLY(is_cache) \
  APPLY(pure_ram) \
  APPLY(pure_cam) \
  APPLY(rpters_in_htree) \
  APPLY(ver_htree_wires_over_array) \
  APPLY(broadcast_addr_din_over_ver_htrees) \
  APPLY(temp) \
  APPLY(ram_cell_tech_type) \
  APPLY(peri_global_tech_type) \
  APPLY(data_arr_ram_cell_tech_type) \
  APPLY(data_arr_peri_global_tech_type) \
  APPLY(tag_arr_ram_cell_tech_type) \
  APPLY(tag_arr_peri_global_tech_type) \
  APPLY(burst_len) \
  APPLY(int_prefetch_w) \
  APPLY(page_sz_bits) \
  APPLY(ic_proj_type) \
  APPLY(wire_is_mat_type) \
  APPLY(wire_os_mat_type) \
  APPLY(wt) \
  APPLY(force_wiretype) \
  APPLY(print_input_args) \
  APPLY(nuca_cache_sz) \
  APPLY(ndbl) \
  APPLY(ndwl) \
  APPLY(nspd) \
  APPLY(ndsam1) \
  APPLY(ndsam2) \
  APPLY(ndcm) \
  APPLY(force_cache_config) \
  APPLY(cache_level) \
  APPLY(cores) \
  APPLY(nuca_bank_count) \
  APPLY(force_nuca_bank) \
  APPLY(delay_wt) \
  APPLY(dynamic_power_wt) \
  APPLY(leakage_power_wt) \
  APPLY(cycle_time_wt) \
  APPLY(area_wt) \
  APPLY(delay_wt_nuca) \
  APPLY(dynamic_power_wt_nuca) \
  APPLY(leakage_power_wt_nuca) \
  APPLY(cycle_time_wt_nuca) \
  APPLY(area_wt_nuca) \
  APPLY(delay_dev) \
  APPLY(dynamic_power_dev) \
  APPLY(leakage_power_dev) \
  APPLY(cycle_time_dev) \
  APPLY(area_dev) \
  APPLY(delay_dev_nuca) \
  APPLY(dynamic_power_dev_nuca) \
  APPLY(leakage_power_dev_nuca) \
  APPLY(cycle_time_dev_nuca) \
  APPLY(area_dev_nuca) \
  APPLY(ed) \
  APPLY(nuca) \
  APPLY(fast_access) \
  APPLY(block_sz) \
  APPLY(tag_assoc) \
  APPLY(data_assoc) \
  APPLY(is_seq_acc) \
  APPLY(fully_assoc) \
  APPLY(nsets) \
  APPLY(print_detail) \
  APPLY(add_ecc_b_) \
  APPLY(throughput) \
  APPLY(latency) \
  APPLY(pipelinable) \
  APPLY(pipeline_stages) \
  APPLY(per_stage_vector) \
  APPLY(with_clock_grid) \
  APPLY(array_power_gated) \
  APPLY(bitline_floating) \
  APPLY(wl_power_gated) \
  APPLY(cl_power_gated) \
  APPLY(interconect_power_gated) \
  APPLY(power_gating) \
  APPLY(perfloss) \
  APPLY(cl_vertical)

namespace {

template <typename T>
void writeSpan(std::ostream& os, const T* value, std::size_t size)
{
  os.write(reinterpret_cast<const char*>(value), size);
}

template <typename T>
void readSpan(std::istream& is, T* value, std::size_t size)
{
  is.read(reinterpret_cast<char*>(value), size);
}

}  // namespace

ResultsDB::ResultsDB()
  : database_path_(createTmpPath()), env_(NULL), dbi_(0), ready_(false)
{
  ready_ = openDatabase();
}

ResultsDB::~ResultsDB()
{
  closeDatabase();
}

ResultsDB& ResultsDB::getInstance()
{
  static ResultsDB instance;
  return instance;
}

bool ResultsDB::get(const InputParameter& input_parameter_key, uca_org_t& uca_org_val)
{
  if (!ready_ || env_ == NULL) {
    return false;
  }

  std::ostringstream key_stream;
  serialize(key_stream, input_parameter_key);
  const std::string key_string = key_stream.str();

  MDB_txn* txn = NULL;
  int rc = mdb_txn_begin(env_, NULL, MDB_RDONLY, &txn);
  if (rc != MDB_SUCCESS) {
    std::cerr << "Failed to open LMDB read transaction: "
              << mdb_strerror(rc) << std::endl;
    return false;
  }

  MDB_val key;
  key.mv_size = key_string.size();
  key.mv_data = const_cast<char*>(key_string.data());

  MDB_val data;
  rc = mdb_get(txn, dbi_, &key, &data);
  if (rc == MDB_NOTFOUND) {
    mdb_txn_abort(txn);
    return false;
  }
  if (rc != MDB_SUCCESS) {
    std::cerr << "Failed to read LMDB entry: " << mdb_strerror(rc) << std::endl;
    mdb_txn_abort(txn);
    return false;
  }

  std::istringstream is(
      std::string(static_cast<const char*>(data.mv_data), data.mv_size));
  deserialize(is, uca_org_val);
  mdb_txn_abort(txn);
  return true;
}

void ResultsDB::put(const InputParameter& input_parameter_key, const uca_org_t& uca_org_val)
{
  if (!ready_ || env_ == NULL) {
    return;
  }

  std::ostringstream key_stream;
  serialize(key_stream, input_parameter_key);
  const std::string key_string = key_stream.str();

  std::ostringstream value_stream;
  serialize(value_stream, uca_org_val);
  const std::string value_string = value_stream.str();

  MDB_txn* txn = NULL;
  int rc = mdb_txn_begin(env_, NULL, 0, &txn);
  if (rc != MDB_SUCCESS) {
    std::cerr << "Failed to open LMDB write transaction: "
              << mdb_strerror(rc) << std::endl;
    return;
  }

  MDB_val key;
  key.mv_size = key_string.size();
  key.mv_data = const_cast<char*>(key_string.data());

  MDB_val data;
  data.mv_size = value_string.size();
  data.mv_data = const_cast<char*>(value_string.data());

  rc = mdb_put(txn, dbi_, &key, &data, 0);
  if (rc != MDB_SUCCESS) {
    std::cerr << "Failed to write LMDB entry: " << mdb_strerror(rc) << std::endl;
    mdb_txn_abort(txn);
    return;
  }

  rc = mdb_txn_commit(txn);
  if (rc != MDB_SUCCESS) {
    std::cerr << "Failed to commit LMDB transaction: "
              << mdb_strerror(rc) << std::endl;
  }
}

bool ResultsDB::openDatabase()
{
  int rc = mdb_env_create(&env_);
  if (rc != MDB_SUCCESS) {
    std::cerr << "Could not create LMDB environment: "
              << mdb_strerror(rc) << std::endl;
    env_ = NULL;
    return false;
  }

  rc = mdb_env_set_maxdbs(env_, 1);
  if (rc != MDB_SUCCESS) {
    std::cerr << "Failed to configure LMDB max DB count: "
              << mdb_strerror(rc) << std::endl;
    closeDatabase();
    return false;
  }

  rc = mdb_env_set_mapsize(env_, 256ULL * 1024ULL * 1024ULL);
  if (rc != MDB_SUCCESS) {
    std::cerr << "Failed to configure LMDB map size: "
              << mdb_strerror(rc) << std::endl;
    closeDatabase();
    return false;
  }

  const std::string db_path = database_path_.string();
  rc = mdb_env_open(env_, db_path.c_str(), MDB_NOSUBDIR, 0664);
  if (rc != MDB_SUCCESS) {
    std::cerr << "Failed to open LMDB database at " << db_path << ": "
              << mdb_strerror(rc) << std::endl;
    closeDatabase();
    return false;
  }

  MDB_txn* txn = NULL;
  rc = mdb_txn_begin(env_, NULL, 0, &txn);
  if (rc != MDB_SUCCESS) {
    std::cerr << "Failed to create LMDB setup transaction: "
              << mdb_strerror(rc) << std::endl;
    closeDatabase();
    return false;
  }

  rc = mdb_dbi_open(txn, "results", MDB_CREATE, &dbi_);
  if (rc != MDB_SUCCESS) {
    std::cerr << "Failed to open LMDB results DBI: "
              << mdb_strerror(rc) << std::endl;
    mdb_txn_abort(txn);
    closeDatabase();
    return false;
  }

  rc = mdb_txn_commit(txn);
  if (rc != MDB_SUCCESS) {
    std::cerr << "Failed to commit LMDB setup transaction: "
              << mdb_strerror(rc) << std::endl;
    closeDatabase();
    return false;
  }

  return true;
}

void ResultsDB::closeDatabase()
{
  if (dbi_ != 0 && env_ != NULL) {
    mdb_dbi_close(env_, dbi_);
    dbi_ = 0;
  }
  if (env_ != NULL) {
    mdb_env_close(env_);
    env_ = NULL;
  }
  ready_ = false;
}

std::filesystem::path ResultsDB::createTmpPath() const
{
  const char* tmpdir = std::getenv("TMPDIR");
  if (tmpdir == NULL || tmpdir[0] == '\0') {
    tmpdir = std::getenv("TEMPDIR");
  }
  if (tmpdir == NULL || tmpdir[0] == '\0') {
    tmpdir = "/tmp";
  }

  const char* user = std::getenv("USER");
  if (user == NULL || user[0] == '\0') {
    user = "unknown";
  }

  return std::filesystem::path(tmpdir) /
         std::string("mcpat-").append(user).append(".db");
}

template <typename T>
void ResultsDB::writeScalar(std::ostream& os, const T& value)
{
  writeSpan(os, &value, sizeof(T));
}

template <typename T>
void ResultsDB::readScalar(std::istream& is, T& value)
{
  readSpan(is, &value, sizeof(T));
}

template <typename T>
void ResultsDB::writePointer(std::ostream& os, const T* value)
{
  const bool present = (value != NULL);
  writeScalar(os, present);
  if (present) {
    serialize(os, *value);
  }
}

template <typename T>
void ResultsDB::readPointer(std::istream& is, T*& value)
{
  bool present = false;
  readScalar(is, present);
  if (!present) {
    value = NULL;
    return;
  }

  value = new T();
  deserialize(is, *value);
}

void ResultsDB::writeVector(std::ostream& os, const std::vector<double>& values)
{
  const std::vector<double>::size_type size = values.size();
  writeScalar(os, size);
  if (size != 0) {
    writeSpan(os, values.data(), size * sizeof(double));
  }
}

void ResultsDB::readVector(std::istream& is, std::vector<double>& values)
{
  std::vector<double>::size_type size = 0;
  readScalar(is, size);
  values.resize(size);
  if (size != 0) {
    readSpan(is, values.data(), size * sizeof(double));
  }
}

void ResultsDB::serialize(std::ostream& os, const InputParameter& param)
{
#define WRITE_FIELD(field) writeScalar(os, param.field);
  MCPAT_INPUT_PARAMETER_FIELDS(WRITE_FIELD)
#undef WRITE_FIELD
  writeVector(os, param.dvs_voltage);
  writeScalar(os, param.long_channel_device);
}

void ResultsDB::deserialize(std::istream& is, InputParameter& param)
{
#define READ_FIELD(field) readScalar(is, param.field);
  MCPAT_INPUT_PARAMETER_FIELDS(READ_FIELD)
#undef READ_FIELD
  readVector(is, param.dvs_voltage);
  readScalar(is, param.long_channel_device);
}

void ResultsDB::serialize(std::ostream& os, const uca_org_t& param)
{
  const std::size_t start = offsetof(uca_org_t, access_time);
  const std::size_t end =
      offsetof(uca_org_t, data_array) + sizeof(results_mem_array);
  writeSpan(
      os,
      reinterpret_cast<const char*>(&param) + start,
      end - start);

  writePointer(os, param.tag_array2);
  writePointer(os, param.data_array2);

  const std::vector<uca_org_t*>::size_type queue_size = param.uca_q.size();
  writeScalar(os, queue_size);
  for (std::vector<uca_org_t*>::size_type i = 0; i < queue_size; ++i) {
    writePointer(os, param.uca_q[i]);
  }

  writePointer(os, param.uca_pg_reference);
}

void ResultsDB::deserialize(std::istream& is, uca_org_t& param)
{
  const std::size_t start = offsetof(uca_org_t, access_time);
  const std::size_t end =
      offsetof(uca_org_t, data_array) + sizeof(results_mem_array);
  readSpan(is, reinterpret_cast<char*>(&param) + start, end - start);

  readPointer(is, param.tag_array2);
  readPointer(is, param.data_array2);

  std::vector<uca_org_t*>::size_type queue_size = 0;
  readScalar(is, queue_size);
  param.uca_q.resize(queue_size);
  for (std::vector<uca_org_t*>::size_type i = 0; i < queue_size; ++i) {
    readPointer(is, param.uca_q[i]);
  }

  readPointer(is, param.uca_pg_reference);
}

void ResultsDB::serialize(std::ostream& os, const mem_array& param)
{
  const std::size_t part1 =
      offsetof(mem_array, power_matchline_to_wordline_drv) + sizeof(powerDef);
  writeSpan(os, reinterpret_cast<const char*>(&param), part1);

  writePointer(os, param.arr_min);

  const std::size_t start = offsetof(mem_array, wt);
  const std::size_t end =
      offsetof(mem_array, long_channel_leakage_reduction_memcell) +
      sizeof(double);
  writeSpan(
      os,
      reinterpret_cast<const char*>(&param) + start,
      end - start);
}

void ResultsDB::deserialize(std::istream& is, mem_array& param)
{
  const std::size_t part1 =
      offsetof(mem_array, power_matchline_to_wordline_drv) + sizeof(powerDef);
  readSpan(is, reinterpret_cast<char*>(&param), part1);

  readPointer(is, param.arr_min);

  const std::size_t start = offsetof(mem_array, wt);
  const std::size_t end =
      offsetof(mem_array, long_channel_leakage_reduction_memcell) +
      sizeof(double);
  readSpan(is, reinterpret_cast<char*>(&param) + start, end - start);
}

void ResultsDB::serialize(std::ostream& os, const min_values_t& param)
{
  writeSpan(os, reinterpret_cast<const char*>(&param), sizeof(min_values_t));
}

void ResultsDB::deserialize(std::istream& is, min_values_t& param)
{
  readSpan(is, reinterpret_cast<char*>(&param), sizeof(min_values_t));
}

#undef MCPAT_INPUT_PARAMETER_FIELDS

#endif
