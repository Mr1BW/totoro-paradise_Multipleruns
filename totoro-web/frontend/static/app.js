/**
 * Totoro Web 前端逻辑
 */

const API_BASE = '';

// DOM 元素引用
const els = {
    qrLoading: document.getElementById('qr-loading'),
    qrImage: document.getElementById('qr-image'),
    qrError: document.getElementById('qr-error'),
    loginActions: document.getElementById('login-actions'),
    loginStatus: document.getElementById('login-status'),
    loginSection: document.getElementById('login-section'),
    userSection: document.getElementById('user-section'),
    calendarSection: document.getElementById('calendar-section'),
    logContainer: document.getElementById('log-container'),
    btnCheckScan: document.getElementById('btn-check-scan'),
    btnRefreshQr: document.getElementById('btn-refresh-qr'),
    btnLogout: document.getElementById('btn-logout'),
    btnClearLog: document.getElementById('btn-clear-log'),
    // 日历
    calendarGrid: document.getElementById('calendar-grid'),
    calendarMonthLabel: document.getElementById('calendar-month-label'),
    btnPrevMonth: document.getElementById('btn-prev-month'),
    btnNextMonth: document.getElementById('btn-next-month'),
    calendarSummary: document.getElementById('calendar-summary'),
    // 弹窗
    makeupModal: document.getElementById('makeup-modal'),
    modalDate: document.getElementById('modal-date'),
    modalStatus: document.getElementById('modal-status'),
    modalRouteSelect: document.getElementById('modal-route-select'),
    btnCloseModal: document.getElementById('btn-close-modal'),
    btnCancelMakeup: document.getElementById('btn-cancel-makeup'),
    btnConfirmMakeup: document.getElementById('btn-confirm-makeup'),
    modalResult: document.getElementById('modal-result'),
    modalStartTime: document.getElementById('modal-start-time'),
    modalDuration: document.getElementById('modal-duration'),
    modalDurationLabel: document.getElementById('modal-duration-label'),
    modalEndTime: document.getElementById('modal-end-time'),
    modalRecordDetail: document.getElementById('modal-record-detail'),
    modalRunForm: document.getElementById('modal-run-form'),
    detailMileage: document.getElementById('detail-mileage'),
    detailUsedTime: document.getElementById('detail-used-time'),
    detailAvgSpeed: document.getElementById('detail-avg-speed'),
    detailStatus: document.getElementById('detail-status'),
};

let currentQrUuid = null;
let currentSession = null;
let currentRunPaper = null;

// ============================================================================
// 日历状态
// ============================================================================

let calendarState = {
    currentDate: new Date(),
    records: {},      // { "2026-03-01": { mileage, usedTime, status }, ... }
    runPointList: [], // 可用路线列表
};

let selectedMakeupDate = null;

// ============================================================================
// 工具函数
// ============================================================================

function log(message, type = 'info') {
    const div = document.createElement('div');
    div.className = `log-entry log-${type}`;
    const time = new Date().toLocaleTimeString();
    div.textContent = `[${time}] ${message}`;
    els.logContainer.appendChild(div);
    els.logContainer.scrollTop = els.logContainer.scrollHeight;
    console.log(`[${type}] ${message}`);
}

function showError(element, message) {
    element.textContent = message;
    element.style.display = 'block';
}

function hideError(element) {
    element.style.display = 'none';
}

function setLoading(element, loading) {
    element.disabled = loading;
    element.style.opacity = loading ? '0.6' : '1';
}

function formatDate(d) {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function computeAvgSpeed(mileage, usedTime) {
    // 根据距离(km)和用时(HH:MM:SS)计算平均配速(km/h)
    if (!mileage || !usedTime) return null;
    try {
        const miles = parseFloat(mileage);
        const parts = usedTime.split(':');
        if (parts.length !== 3) return null;
        const hours = parseInt(parts[0], 10);
        const minutes = parseInt(parts[1], 10);
        const seconds = parseInt(parts[2], 10);
        const totalHours = hours + minutes / 60 + seconds / 3600;
        if (totalHours <= 0) return null;
        const speed = miles / totalHours;
        return speed.toFixed(2);
    } catch (e) {
        return null;
    }
}

// ============================================================================
// API 调用
// ============================================================================

async function apiGet(path) {
    const resp = await fetch(`${API_BASE}${path}`);
    return resp.json();
}

async function apiPost(path, body) {
    const resp = await fetch(`${API_BASE}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    return resp.json();
}

async function apiDelete(path) {
    const resp = await fetch(`${API_BASE}${path}`, { method: 'DELETE' });
    return resp.json();
}

// ============================================================================
// 二维码 & 登录
// ============================================================================

async function loadQrCode() {
    els.qrLoading.style.display = 'block';
    els.qrImage.style.display = 'none';
    hideError(els.qrError);
    els.loginActions.style.display = 'none';
    currentQrUuid = null;

    try {
        const data = await apiGet('/api/auth/qr');
        currentQrUuid = data.uuid;
        els.qrImage.src = data.imgUrl;
        els.qrImage.style.display = 'block';
        els.qrLoading.style.display = 'none';
        els.loginActions.style.display = 'block';
        log('二维码加载成功');

        startSsePolling(data.uuid);
    } catch (e) {
        els.qrLoading.style.display = 'none';
        showError(els.qrError, `加载二维码失败: ${e.message}`);
        log('二维码加载失败', 'error');
    }
}

function startSsePolling(uuid) {
    const evtSource = new EventSource(`${API_BASE}/api/auth/scan/${uuid}/sse`);

    evtSource.addEventListener('scanned', (e) => {
        const data = JSON.parse(e.data);
        log('微信扫码成功，获取到 code');
        evtSource.close();
        doLogin(data.code);
    });

    evtSource.addEventListener('timeout', () => {
        log('扫码超时，请刷新二维码', 'warn');
        evtSource.close();
    });

    evtSource.addEventListener('error', () => {
        evtSource.close();
    });
}

async function doLogin(code) {
    els.loginStatus.textContent = '正在登录...';
    setLoading(els.btnCheckScan, true);
    log('正在使用 code 登录龙猫服务器...');

    try {
        const result = await apiPost('/api/auth/login', { code });
        if (result.success && result.session) {
            currentSession = result.session;
            log(`登录成功！欢迎，${result.session.stuName}`);
            els.loginStatus.textContent = '登录成功！';
            showUserInfo(result.session);
            loadRunPaper();
            loadCalendarData();
        } else {
            els.loginStatus.textContent = `登录失败: ${result.message}`;
            log(`登录失败: ${result.message}`, 'error');
        }
    } catch (e) {
        els.loginStatus.textContent = `登录异常: ${e.message}`;
        log(`登录异常: ${e.message}`, 'error');
    } finally {
        setLoading(els.btnCheckScan, false);
    }
}

// ============================================================================
// 用户信息展示
// ============================================================================

function showUserInfo(session) {
    els.loginSection.style.display = 'none';
    els.userSection.style.display = 'block';
    els.calendarSection.style.display = 'block';

    document.getElementById('user-name').textContent = session.stuName || '-';
    document.getElementById('user-number').textContent = session.stuNumber || '-';
    document.getElementById('user-school').textContent = session.schoolName || '-';
    document.getElementById('user-campus').textContent = session.campusName || '-';
}

function showLoginSection() {
    els.loginSection.style.display = 'block';
    els.userSection.style.display = 'none';
    els.calendarSection.style.display = 'none';
    currentSession = null;
    loadQrCode();
}

async function checkSession() {
    try {
        const result = await apiGet('/api/session/check');
        if (result.success) {
            currentSession = result.data;
            log(`已检测到登录状态: ${result.data.stuName}`);
            showUserInfo(result.data);
            loadRunPaper();
            loadCalendarData();
        } else {
            loadQrCode();
        }
    } catch (e) {
        loadQrCode();
    }
}

async function logout() {
    try {
        await apiDelete('/api/session');
        log('已退出登录');
        showLoginSection();
    } catch (e) {
        log('退出失败', 'error');
    }
}

// ============================================================================
// 跑步任务
// ============================================================================

async function loadRunPaper() {
    try {
        const result = await apiGet('/api/run/paper');
        if (!result.success) {
            log(`获取跑步任务失败: ${result.message}`, 'error');
            return;
        }
        currentRunPaper = result.data;
        displayRunPaper(result.data);
        // 保存路线列表供日历使用
        calendarState.runPointList = result.data.runPointList || [];
    } catch (e) {
        log(`获取跑步任务异常: ${e.message}`, 'error');
    }
}

function displayRunPaper(data) {
    // 保存路线列表供日历使用
    calendarState.runPointList = data.runPointList || [];
}

// ============================================================================
// 日历功能
// ============================================================================

async function loadCalendarData() {
    try {
        log('正在加载本学期跑步数据...');
        const result = await apiGet('/api/history/calendar');
        if (!result.success) {
            log(`加载日历数据失败: ${result.message}`, 'error');
            return;
        }
        calendarState.records = result.data.records || {};
        log(`加载完成，本学期已有 ${Object.keys(calendarState.records).length} 天跑步记录`);
        renderCalendar();
    } catch (e) {
        log(`加载日历数据异常: ${e.message}`, 'error');
    }
}

function renderCalendar() {
    const year = calendarState.currentDate.getFullYear();
    const month = calendarState.currentDate.getMonth();

    els.calendarMonthLabel.textContent = `${year}年${month + 1}月`;

    // 计算该月第一天和最后一天
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    const startWeekday = firstDay.getDay(); // 0 = 周日

    // 表头
    const weekdays = ['日', '一', '二', '三', '四', '五', '六'];
    let html = '<div class="calendar-row calendar-header-row">';
    weekdays.forEach(d => {
        html += `<div class="calendar-cell calendar-header-cell">${d}</div>`;
    });
    html += '</div>';

    // 日期单元格
    html += '<div class="calendar-row">';

    // 空白填充
    for (let i = 0; i < startWeekday; i++) {
        html += '<div class="calendar-cell calendar-empty"></div>';
    }

    const today = formatDate(new Date());
    let runCount = 0;
    let missCount = 0;

    for (let day = 1; day <= daysInMonth; day++) {
        const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        const record = calendarState.records[dateStr];
        const isToday = dateStr === today;

        let cellClass = 'calendar-cell calendar-day';
        let statusDot = '';
        let clickAttr = `onclick="handleDateClick('${dateStr}')"`;

        if (record) {
            cellClass += ' has-run';
            statusDot = `<span class="day-dot run"></span>`;
            runCount++;
        } else if (dateStr < today) {
            cellClass += ' no-run';
            statusDot = `<span class="day-dot miss"></span>`;
            missCount++;
        }

        if (isToday) {
            cellClass += ' today';
        }

        html += `
            <div class="${cellClass}" ${clickAttr}>
                <span class="day-number">${day}</span>
                ${statusDot}
            </div>
        `;

        // 每周换行
        if ((startWeekday + day) % 7 === 0 && day !== daysInMonth) {
            html += '</div><div class="calendar-row">';
        }
    }

    // 末尾空白填充
    const totalCells = startWeekday + daysInMonth;
    const remaining = 7 - (totalCells % 7);
    if (remaining < 7) {
        for (let i = 0; i < remaining; i++) {
            html += '<div class="calendar-cell calendar-empty"></div>';
        }
    }

    html += '</div>';
    els.calendarGrid.innerHTML = html;

    // 更新统计
    els.calendarSummary.innerHTML = `
        本月：已跑 <span class="stat-run">${runCount}</span> 天，
        未跑 <span class="stat-miss">${missCount}</span> 天
    `;
}

function handleDateClick(dateStr) {
    selectedMakeupDate = dateStr;
    const record = calendarState.records[dateStr];

    els.modalDate.textContent = dateStr;
    els.modalResult.textContent = '';
    els.modalResult.className = 'status';

    if (record) {
        // ========== 已跑步：只读模式 ==========
        els.modalStatus.textContent = '已跑步';
        els.modalStatus.className = 'text-success';

        // 显示详情
        els.modalRecordDetail.style.display = 'block';
        els.detailMileage.textContent = `${record.mileage} km`;
        els.detailUsedTime.textContent = record.usedTime;

        // 根据 mileage 和 usedTime 计算平均配速
        const avgSpeed = computeAvgSpeed(record.mileage, record.usedTime);
        els.detailAvgSpeed.textContent = avgSpeed ? `${avgSpeed} km/h` : '-';

        els.detailStatus.textContent = record.status === '1' ? '有效' : '待确认';

        // 隐藏表单和确认按钮
        els.modalRunForm.style.display = 'none';
        els.btnConfirmMakeup.style.display = 'none';
    } else {
        // ========== 未跑步：跑步模式 ==========
        els.modalStatus.textContent = '未跑步';
        els.modalStatus.className = 'text-error';

        // 隐藏详情
        els.modalRecordDetail.style.display = 'none';

        // 显示表单
        els.modalRunForm.style.display = 'block';

        // 填充路线选择
        els.modalRouteSelect.innerHTML = '';
        calendarState.runPointList.forEach((route, idx) => {
            const option = document.createElement('option');
            option.value = route.pointId;
            option.textContent = route.pointName || `路线 ${idx + 1}`;
            els.modalRouteSelect.appendChild(option);
        });

        // 更新预计结束时间显示
        updateEndTimePreview();

        // 显示确认按钮
        els.btnConfirmMakeup.style.display = 'inline-block';
    }

    els.makeupModal.style.display = 'flex';
}

function updateEndTimePreview() {
    const startTime = els.modalStartTime.value || '06:00';
    const durationMin = parseInt(els.modalDuration.value || '15', 10);
    
    // 计算结束时间（不显示随机波动，只显示基准值）
    const [h, m] = startTime.split(':').map(Number);
    const totalMinutes = h * 60 + m + durationMin;
    const endH = Math.floor(totalMinutes / 60) % 24;
    const endM = totalMinutes % 60;
    
    els.modalDurationLabel.textContent = `${durationMin} 分钟`;
    els.modalEndTime.textContent = `${String(endH).padStart(2, '0')}:${String(endM).padStart(2, '0')}`;
}

async function confirmMakeup() {
    if (!selectedMakeupDate) return;

    // 安全检查：如果该日期已经跑过，禁止再次提交
    if (calendarState.records[selectedMakeupDate]) {
        log(`⚠️ ${selectedMakeupDate} 已经跑过了，不能重复提交`, 'warn');
        els.modalResult.textContent = '该日期已跑步，无法重复提交';
        els.modalResult.className = 'status text-warning';
        return;
    }

    setLoading(els.btnConfirmMakeup, true);
    els.btnConfirmMakeup.textContent = '生成轨迹中...';
    els.modalResult.textContent = '';

    const startTime = els.modalStartTime.value;
    const durationMin = parseInt(els.modalDuration.value, 10);
    const routeId = els.modalRouteSelect.value;

    log(`正在为 ${selectedMakeupDate} 跑步...`);
    log(`   路线: ${routeId}，开始时间: ${startTime}，基准时长: ${durationMin} 分钟`);

    try {
        // ========== Step 1: 生成轨迹 ==========
        log('正在生成 GPS 轨迹...');
        const generateResult = await apiPost('/api/run/generate', {
            routeId: routeId,
            distance: currentRunPaper ? parseFloat(currentRunPaper.mileage || '3.2') : 3.2,
            runDate: selectedMakeupDate,
            startTime: startTime,
            durationMin: durationMin,
        });

        if (!generateResult.success) {
            log(`❌ 生成轨迹失败: ${generateResult.message}`, 'error');
            els.modalResult.textContent = `生成轨迹失败: ${generateResult.message}`;
            els.modalResult.className = 'status text-error';
            return;
        }

        log(`✅ 轨迹生成成功！`);
        log(`   文件: ${generateResult.data.filePath}`);
        log(`   轨迹点数: ${generateResult.data.pointCount}`);
        log(`   预计距离: ${generateResult.data.distance} km`);

        // ========== Step 2: 提交跑步记录 ==========
        els.btnConfirmMakeup.textContent = '提交中...';
        log('正在提交跑步记录...');

        const submitResult = await apiPost('/api/run/submit', {
            routeId: routeId,
            runDate: selectedMakeupDate,
        });

        if (submitResult.success) {
            log(`✅ ${selectedMakeupDate} 跑步提交成功！`);
            log(`   距离: ${submitResult.data.distance} km`);
            log(`   实际用时: ${submitResult.data.usedTime}`);
            log(`   配速: ${submitResult.data.avgSpeed} km/h`);
            els.modalResult.textContent = '跑步成功！';
            els.modalResult.className = 'status text-success';
            // 刷新日历
            await loadCalendarData();
            setTimeout(() => {
                els.makeupModal.style.display = 'none';
            }, 1500);
        } else {
            log(`❌ 提交失败: ${submitResult.message}`, 'error');
            els.modalResult.textContent = `提交失败: ${submitResult.message}`;
            els.modalResult.className = 'status text-error';
        }
    } catch (e) {
        log(`跑步异常: ${e.message}`, 'error');
        els.modalResult.textContent = `异常: ${e.message}`;
    } finally {
        setLoading(els.btnConfirmMakeup, false);
        els.btnConfirmMakeup.textContent = '确认跑步';
    }
}

function closeModal() {
    els.makeupModal.style.display = 'none';
    selectedMakeupDate = null;
}

function prevMonth() {
    calendarState.currentDate.setMonth(calendarState.currentDate.getMonth() - 1);
    renderCalendar();
}

function nextMonth() {
    calendarState.currentDate.setMonth(calendarState.currentDate.getMonth() + 1);
    renderCalendar();
}

// ============================================================================
// 事件绑定
// ============================================================================

els.btnCheckScan.addEventListener('click', async () => {
    if (!currentQrUuid) return;
    setLoading(els.btnCheckScan, true);
    log('正在查询扫码状态...');

    try {
        const result = await apiGet(`/api/auth/scan/${currentQrUuid}`);
        if (result.scanned && result.code) {
            log('检测到扫码，开始登录...');
            await doLogin(result.code);
        } else {
            els.loginStatus.textContent = result.message || '未检测到扫码';
            log(result.message || '未检测到扫码', 'warn');
        }
    } catch (e) {
        log(`查询失败: ${e.message}`, 'error');
    } finally {
        setLoading(els.btnCheckScan, false);
    }
});

els.btnRefreshQr.addEventListener('click', () => {
    log('刷新二维码');
    loadQrCode();
});

els.btnLogout.addEventListener('click', logout);
els.btnClearLog.addEventListener('click', () => {
    els.logContainer.innerHTML = '';
});

// 弹窗时间/时长变化时更新预计结束时间
els.modalStartTime.addEventListener('change', updateEndTimePreview);
els.modalDuration.addEventListener('input', updateEndTimePreview);

// 日历事件
els.btnPrevMonth.addEventListener('click', prevMonth);
els.btnNextMonth.addEventListener('click', nextMonth);

// 弹窗事件
els.btnCloseModal.addEventListener('click', closeModal);
els.btnCancelMakeup.addEventListener('click', closeModal);
els.btnConfirmMakeup.addEventListener('click', confirmMakeup);
els.makeupModal.addEventListener('click', (e) => {
    if (e.target === els.makeupModal) closeModal();
});

// ============================================================================
// 暴露全局函数（供 HTML onclick 调用）
// ============================================================================

window.handleDateClick = handleDateClick;

// ============================================================================
// 初始化
// ============================================================================

log('Totoro Web 已加载');
checkSession();
