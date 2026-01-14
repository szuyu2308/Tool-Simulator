# Universal Bug Fix TODO (Template) — Fix bất kỳ lỗi nào trả về (Production-grade)

**ROLE: SENIOR PYTHON AUTOMATION ENGINEER**  
You are an expert in Python, ADB, and Image Processing. You focus on robust error handling, clean code (PEP8), and performance optimization.

> Mục tiêu: Quy trình chuẩn hoá để xử lý **bất kỳ lỗi nào** (crash, timeout, sai dữ liệu, lỗi dependency, performance, v.v.) theo chu trình:
> **Kiểm tra → Sửa lỗi → Kiểm tra → Debug → Kiểm thử → Xác thực → Phân tích lỗi có thể gặp → Tối ưu lần cuối → Kiểm thử lần cuối → Ra sản phẩm**

---

## 0) INPUT CHUẨN (Bắt buộc có trước khi bắt đầu)
- [ ] Error message/stack trace **đầy đủ** (không cắt).
- [ ] Bối cảnh: hành động nào gây lỗi (steps), input/output, tần suất.
- [ ] Môi trường: OS, version, runtime, config, dependencies, network.
- [ ] Mức độ ảnh hưởng: crash hay fail 1 request/job? tỉ lệ? impact user?
- [ ] Expected behavior (kỳ vọng đúng là gì).

**Deliverable:** “Bug Report tối thiểu” đủ tái hiện.

---

## 1) KIỂM TRA (Triage & Reproduce)
### 1.1 Tái hiện lỗi
- [ ] Tạo kịch bản reproduce *deterministic* (càng ít bước càng tốt).
- [ ] Nếu không reproduce được: chuyển sang **observability-first** (mục 2.3).

### 1.2 Phân loại lỗi theo cấp độ
- [ ] Crash toàn process / service down
- [ ] Fail request/job nhưng hệ thống còn chạy
- [ ] Sai dữ liệu (silent corruption)
- [ ] Performance/timeout
- [ ] Security/permission

### 1.3 Khoanh vùng phạm vi
- [ ] Xác định module/entrypoint.
- [ ] Xác định input gây lỗi (minimal failing input).
- [ ] Xác định thay đổi gần nhất (deploy, config, dependency update).

**Deliverable:** Checklist reproduce + phạm vi ảnh hưởng.

---

## 2) KIỂM TRA (Instrumentation trước khi sửa sâu)
### 2.1 Bật logging/trace đúng cách
- [ ] Mỗi request/job có **correlation-id**.
- [ ] Log: input shape (không log dữ liệu nhạy cảm), config quan trọng, timing.

### 2.2 Thu thập bằng chứng
- [ ] Log trước/sau điểm lỗi.
- [ ] Core dump/heap dump nếu cần.
- [ ] Metrics liên quan (error rate, latency p95/p99, memory, CPU).

### 2.3 Nếu không reproduce được
- [ ] Thêm guard log + sampling + feature flag để bật debug production an toàn.
- [ ] Tạo “error fingerprint” để nhóm lỗi (hash theo stack/message).

**Deliverable:** Evidence đủ để phân tích nguyên nhân.

---

## 3) DEBUG (Root Cause Analysis)
### 3.1 Xác định loại nguyên nhân
- [ ] Logic bug (null/None, index, race condition)
- [ ] Input validation thiếu (schema/format bất ngờ)
- [ ] External dependency failure (network, DB, API)
- [ ] Resource issue (CPU/RAM/Disk/FD leak)
- [ ] Concurrency/deadlock
- [ ] Config/feature flag sai
- [ ] Version mismatch / backward incompatibility

### 3.2 Viết RCA note (ngắn nhưng rõ)
- [ ] Symptom: thấy gì?
- [ ] Cause: vì sao xảy ra?
- [ ] Trigger: điều kiện kích hoạt?
- [ ] Blast radius: ảnh hưởng gì?

**Deliverable:** RCA note (1–2 đoạn).

---

## 4) THIẾT KẾ SỬA (Fix Plan trước khi code)
### 4.1 Chọn chiến lược xử lý lỗi (error-handling strategy)
- [ ] **Fail-fast** khi không phục hồi được.
- [ ] **Retry có giới hạn** khi lỗi tạm thời.
- [ ] **Fallback** khi có phương án thay thế.
- [ ] **Degrade gracefully** (giảm chức năng nhưng vẫn chạy).
- [ ] **Circuit breaker / rate limit** khi dependency không ổn định.
- [ ] **Idempotency/dedup** nếu retry có thể tạo tác dụng phụ.

### 4.2 Chuẩn hoá “error contract”
- [ ] Error code (taxonomy), message rõ, `retryable` true/false.
- [ ] Không để exception “rò rỉ” làm crash nếu không chủ đích.
- [ ] Mapping lỗi nội bộ → lỗi trả về cho caller/user (không leak secrets).

### 4.3 Định nghĩa tiêu chí hoàn thành
- [ ] Không crash / không corrupt data
- [ ] Đúng output hoặc trả lỗi chuẩn
- [ ] Latency không xấu đi quá ngưỡng
- [ ] Có test cover cho nhánh lỗi

**Deliverable:** Fix plan + acceptance criteria.

---

## 5) SỬA LỖI (Implementation lần 1)
### 5.1 Thay đổi tối thiểu nhưng đúng
- [ ] Thêm validate input (schema/constraints).
- [ ] Wrap lỗi ở boundary (I/O, external calls, parsing).
- [ ] Thêm timeout hợp lý cho I/O.
- [ ] Thêm retry có giới hạn + backoff + jitter cho lỗi tạm thời.
- [ ] Cleanup resource (file/socket/process) bằng context manager/finally.

### 5.2 Chống “failure cascade”
- [ ] Không retry vô hạn.
- [ ] Không log spam (rate limit/sampling).
- [ ] Không swallow lỗi mà không có signal (phải trả error contract).

**Deliverable:** Patch/fix v1.

---

## 6) KIỂM TRA (Sanity check ngay sau sửa)
- [ ] Re-run reproduce case → hết lỗi.
- [ ] Chạy happy path → không regress.
- [ ] Check log/metrics: đủ context, không leak secrets.

**Deliverable:** Evidence (log/test output) chứng minh pass.

---

## 7) KIỂM THỬ (Test coverage có hệ thống)
### 7.1 Unit tests (bắt buộc)
- [ ] Test input invalid → fail-fast đúng contract.
- [ ] Test dependency failure (mock) → retry/fallback đúng policy.
- [ ] Test error mapping → error code/message đúng.
- [ ] Test resource cleanup (không leak).

### 7.2 Integration tests
- [ ] Test với dependency thật hoặc simulator (network/db/fs).
- [ ] Chaos test: delay, drop connection, partial response.
- [ ] Concurrency test nếu có multi-thread/process/async.

### 7.3 Regression tests
- [ ] Thêm test riêng cho bug vừa fix để không tái phát.

**Deliverable:** Test suite + coverage đủ các nhánh lỗi chính.

---

## 8) XÁC THỰC (Validation theo tiêu chí sản phẩm)
- [ ] Validate theo acceptance criteria đã định nghĩa.
- [ ] Validate dữ liệu không bị sai/thiếu (nếu liên quan data).
- [ ] Validate performance: p95/p99 không vượt ngưỡng.
- [ ] Validate observability: logs/metrics/traces đạt chuẩn.

**Deliverable:** Validation report ngắn (What/How/Result).

---

## 9) PHÂN TÍCH “CÁC LỖI CÓ THỂ GẶP” (Universal Failure Modes Checklist)
Dùng checklist này để soi các lỗ tương tự:
- [ ] Timeout/hang (I/O, subprocess, external API)
- [ ] Retry storm / thundering herd
- [ ] Partial failure (trả về nửa dữ liệu)
- [ ] Data corruption thầm lặng (parse sai nhưng không crash)
- [ ] Race condition/deadlock
- [ ] Memory leak / file descriptor leak
- [ ] Disk full / permission denied
- [ ] Backward incompatible change
- [ ] Security: injection, secret leakage, unsafe logs
- [ ] Observability thiếu: không trace được job/request

**Deliverable:** Danh sách rủi ro còn lại + quyết định xử lý (fix now / backlog).

---

## 10) SỬA CODE TỐI ƯU NHẤT LẦN CUỐI (Hardening & Refactor có kiểm soát)
- [ ] Refactor nhỏ để rõ ràng hơn (tách boundary I/O, pure logic).
- [ ] Chuẩn hoá exception types (custom errors) để phân loại chính xác.
- [ ] Tối ưu hot path (tránh I/O thừa, cache hợp lý).
- [ ] Thêm feature flag/config để tune policy không cần sửa code.
- [ ] Bổ sung docs/runbook xử lý sự cố.

**Deliverable:** Patch v2 (hardened).

---

## 11) KIỂM THỬ LẦN CUỐI (Release candidate testing)
- [ ] Chạy toàn bộ unit + integration + regression.
- [ ] Stress test/soak test (chạy lâu) nếu lỗi thuộc stability.
- [ ] Kiểm tra backward compatibility (nếu public API/contract).

**Deliverable:** RC test results + sign-off.

---

## 12) RA SẢN PHẨM (Release & Post-release)
- [ ] Rollout theo từng bước (canary/percentage) nếu production.
- [ ] Monitor error rate, latency, resource, logs sau release.
- [ ] Thiết lập alert theo `error_code` mới (nếu có).
- [ ] Postmortem ngắn nếu lỗi nghiêm trọng: học được gì, phòng ngừa gì.

**Deliverable:** Release note + monitoring plan + rollback plan.

---