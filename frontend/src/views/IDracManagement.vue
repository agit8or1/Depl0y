<template>
  <div class="idrac-page">
    <div class="page-header mb-2">
      <div>
        <h2>iDRAC / iLO Management</h2>
        <p class="text-muted text-sm">Out-of-band hardware control via Redfish — polls every 2 min</p>
      </div>
      <div class="flex gap-1">
        <button @click="pollNow()" class="btn btn-outline btn-sm" :disabled="polling">
          {{ polling ? 'Polling…' : 'Poll Now' }}
        </button>
        <button @click="openAddStandalone()" class="btn btn-primary btn-sm">+ Add Standalone BMC</button>
      </div>
    </div>

    <div v-if="loading" class="loading-spinner"></div>

    <div v-else>
      <!-- ── Dashboard summary ── -->
      <div v-if="allServers.length > 0" class="dashboard mb-3">
        <!-- Stat cards -->
        <div class="stat-cards">
          <div class="stat-card">
            <div class="stat-card__value">{{ dash.total }}</div>
            <div class="stat-card__label">Total</div>
          </div>
          <div class="stat-card stat-card--on">
            <div class="stat-card__value">{{ dash.on }}</div>
            <div class="stat-card__label">Online</div>
          </div>
          <div class="stat-card stat-card--ok">
            <div class="stat-card__value">{{ dash.healthy }}</div>
            <div class="stat-card__label">Healthy</div>
          </div>
          <div class="stat-card stat-card--warn" v-if="dash.warning > 0">
            <div class="stat-card__value">{{ dash.warning }}</div>
            <div class="stat-card__label">Warning</div>
          </div>
          <div class="stat-card stat-card--crit" v-if="dash.critical > 0">
            <div class="stat-card__value">{{ dash.critical }}</div>
            <div class="stat-card__label">Critical</div>
          </div>
          <div class="stat-card stat-card--err" v-if="dash.unreachable > 0">
            <div class="stat-card__value">{{ dash.unreachable }}</div>
            <div class="stat-card__label">Unreachable</div>
          </div>
          <div class="stat-card stat-card--ssh" v-if="dash.sshMode > 0">
            <div class="stat-card__value">{{ dash.sshMode }}</div>
            <div class="stat-card__label">SSH Mode</div>
          </div>
          <div class="stat-card stat-card--muted" v-if="dash.unconfigured > 0">
            <div class="stat-card__value">{{ dash.unconfigured }}</div>
            <div class="stat-card__label">Unconfigured</div>
          </div>
        </div>

        <!-- Charts row -->
        <div class="dash-charts mt-2">
          <div class="dash-chart-card">
            <div class="dash-chart-title">Health</div>
            <div class="dash-chart-wrap">
              <Doughnut :data="healthChartData" :options="dashChartOptions" />
            </div>
          </div>
          <div class="dash-chart-card">
            <div class="dash-chart-title">Power State</div>
            <div class="dash-chart-wrap">
              <Doughnut :data="powerStateChartData" :options="dashChartOptions" />
            </div>
          </div>
          <div class="dash-chart-card dash-chart-card--wide">
            <div class="dash-chart-title">Temperature ({{ tempLabel }}) — max per server</div>
            <div class="dash-chart-wrap dash-chart-wrap--bar">
              <Bar :data="tempBarData" :options="tempBarOptions" />
            </div>
          </div>
        </div>

        <!-- Alerts strip -->
        <div v-if="alertedServers.length > 0" class="alert-strip mt-2">
          <span class="alert-strip__label">⚠ Alerts:</span>
          <button v-for="s in alertedServers" :key="s._key" @click="jumpToServer(s)" class="alert-chip" :class="`alert-chip--${alertLevel(s)}`">
            {{ s.name }}
            <span class="text-xs ml-1">{{ alertReason(s) }}</span>
          </button>
        </div>

        <!-- Compact overview table -->
        <div class="overview-table-wrap mt-2">
          <table class="table table--compact">
            <thead>
              <tr>
                <th>Server</th>
                <th>Type</th>
                <th>Power</th>
                <th>Health</th>
                <th>Temp</th>
                <th>Watts</th>
                <th>Model</th>
                <th>Last Poll</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="srv in allServers" :key="srv._key"
                  :class="{ 'row-critical': alertLevel(srv) === 'crit', 'row-warning': alertLevel(srv) === 'warn' }">
                <td class="text-xs font-bold">{{ srv.name }}</td>
                <td class="text-xs">
                  <span :class="['type-pill', `type-pill--${srv._stype}`]">{{ typeLabel(srv._stype) }}</span>
                </td>
                <td class="text-xs">
                  <span v-if="srv._status?.power_state" :class="['power-badge', srv._status.power_state === 'On' ? 'power-on' : 'power-off']">{{ srv._status.power_state }}</span>
                  <span v-else class="text-muted">—</span>
                </td>
                <td class="text-xs">
                  <span v-if="srv._status?.error && !srv._useSSH" class="error-inline">⚠ Unreachable</span>
                  <span v-else-if="srv._status?.health" :class="['health-badge', `health-${(srv._status.health||'unknown').toLowerCase()}`]">{{ srv._status.health }}</span>
                  <span v-else class="text-muted">—</span>
                </td>
                <td class="text-xs">
                  <span v-if="srv._status?.max_temp_c != null" :class="['temp-badge', srv._status.max_temp_c >= 75 ? 'temp-hot' : srv._status.max_temp_c >= 55 ? 'temp-warm' : 'temp-ok']">
                    {{ toDisplay(srv._status.max_temp_c) }}{{ tempLabel }}
                  </span>
                  <span v-else class="text-muted">—</span>
                </td>
                <td class="text-xs text-muted">
                  {{ srv._status?.consumed_watts != null ? srv._status.consumed_watts + 'W' : '—' }}
                </td>
                <td class="text-xs text-muted">{{ srv._status?.model || '—' }}</td>
                <td class="text-xs text-muted">{{ srv._status?.last_polled ? formatRelative(srv._status.last_polled) : '—' }}</td>
                <td class="text-xs">
                  <button @click="srv._expanded ? collapseServer(srv) : expandServer(srv)" class="btn btn-outline btn-sm" style="padding:0.1rem 0.5rem;font-size:0.7rem">
                    {{ srv._expanded ? 'Close' : 'Details' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ── Server list ── -->
      <template v-if="allServers.length > 0">
        <div v-for="srv in allServers" :key="srv._key" :id="`srv-card-${srv._key}`" class="server-card mb-2">
          <!-- Status row (always visible) -->
          <div class="status-row">
            <div class="status-left">
              <span class="srv-name">{{ srv.name }}</span>
              <span :class="['type-pill', `type-pill--${srv._stype}`]">{{ typeLabel(srv._stype) }}</span>
              <span v-if="srv.idrac_type" :class="['type-pill', `type-pill--bmctype`]" :title="srv.idrac_hostname">{{ bmcTypeLabel(srv.idrac_type) }}</span>
              <span v-if="srv.idrac_hostname" class="text-xs text-muted font-mono">{{ srv.idrac_hostname }}</span>
              <span v-if="srv._status" :class="['health-badge', `health-${(srv._status.health || 'unknown').toLowerCase()}`]">
                {{ srv._status.health || 'Unknown' }}
              </span>
              <span v-if="srv._status?.power_state" :class="['power-badge', srv._status.power_state === 'On' ? 'power-on' : 'power-off']">
                {{ srv._status.power_state }}
              </span>
              <span v-if="srv._status?.error && !srv._useSSH" class="error-inline" title="BMC unreachable">⚠ Unreachable</span>
              <span v-if="!srv._status && srv.idrac_hostname && !srv._useSSH" class="text-muted text-xs">Pending first poll…</span>
            </div>
            <div class="status-right flex gap-1">
              <span v-if="srv._useSSH" class="type-pill type-pill--pbs" title="Data source: SSH">SSH</span>
              <span v-if="srv._status?.last_polled" class="text-xs text-muted">{{ formatRelative(srv._status.last_polled) }}</span>
              <template v-if="srv._stype === 'standalone'">
                <button @click="openEditStandalone(srv)" class="btn btn-outline btn-sm">Edit</button>
                <button @click="deleteStandalone(srv)" class="btn btn-danger btn-sm">Delete</button>
              </template>
              <template v-else-if="srv._stype === 'pbs'">
                <button @click="openConfigBMC(srv)" class="btn btn-outline btn-sm">{{ srv.idrac_hostname ? 'Edit BMC' : 'Configure BMC' }}</button>
                <button @click="deletePBS(srv)" class="btn btn-danger btn-sm">Delete</button>
              </template>
              <template v-else>
                <button @click="openConfigBMC(srv)" class="btn btn-outline btn-sm">{{ srv.idrac_hostname ? 'Edit BMC' : 'Configure BMC' }}</button>
              </template>
              <a v-if="srv.idrac_hostname" :href="`https://${srv.idrac_hostname}:${srv.idrac_port || 443}`" target="_blank" rel="noopener" class="btn btn-outline btn-sm">Launch ↗</a>
              <button @click="testConnection(srv)" class="btn btn-outline btn-sm">Test</button>
              <button @click="srv._expanded ? collapseServer(srv) : expandServer(srv)" class="btn btn-primary btn-sm" :disabled="srv._loading">
                {{ srv._loading ? 'Loading…' : (srv._expanded ? 'Close' : 'Details') }}
              </button>
            </div>
          </div>

          <!-- No BMC configured notice -->
          <div v-if="!srv.idrac_hostname && srv._stype !== 'standalone'" class="no-bmc-notice">
            No BMC configured — click "Configure BMC" to add iDRAC/iLO credentials.
          </div>

          <!-- Details panel (expanded) — always visible when expanded -->
          <div v-if="srv._expanded" class="details-panel">
            <!-- Loading bar — always shown while fetching, even with cached data -->
            <div v-if="srv._loading" class="details-fetch-bar">
              <div class="details-fetch-bar__fill"></div>
            </div>

            <div class="details-close">
              <button @click="collapseServer(srv)" class="btn btn-outline btn-sm">✕ Close</button>
            </div>

            <!-- Full loading state (no cached data yet) -->
            <div v-if="srv._loading && !srv._info" class="details-loading">
              <div class="loading-spinner"></div>
              <span class="text-muted text-sm">Connecting to BMC…</span>
            </div>
            <div v-if="srv._error" class="error-box flex gap-1 mb-1" style="align-items:center;justify-content:space-between">
              <span>{{ srv._error }}</span>
              <button @click="loadServerDetail(srv)" class="btn btn-outline btn-sm" :disabled="srv._loading">
                {{ srv._loading ? 'Retrying…' : 'Retry' }}
              </button>
            </div>

            <!-- Tabs -->
            <div v-if="srv._info" class="detail-tabs">
              <button v-for="tab in ['overview','hardware','sensors','network','firmware','logs']" :key="tab"
                @click="switchTab(srv, tab)"
                :class="['tab-btn', srv._activeTab === tab ? 'tab-btn--active' : '']">
                {{ tab.charAt(0).toUpperCase() + tab.slice(1) }}
              </button>
            </div>

            <!-- TAB: Overview -->
            <div v-if="srv._info && srv._activeTab === 'overview'">

              <!-- ── Health issues summary ─────────────────────────────── -->
              <div v-if="(srv._info?.health && srv._info.health !== 'OK' && srv._info.health !== 'Unknown') || (srv._status?.error && !srv._useSSH)" class="health-issues-panel">
                <div class="health-issues-title">
                  <span v-if="srv._info?.health === 'Critical' || (srv._status?.error && !srv._useSSH)" class="hi-badge hi-badge--crit">⚠ Critical</span>
                  <span v-else class="hi-badge hi-badge--warn">⚠ Warning</span>
                  Detected issues
                </div>

                <!-- Specific component issues found -->
                <ul v-if="healthIssues(srv).length" class="health-issues-list">
                  <li v-for="issue in healthIssues(srv)" :key="issue.label" :class="issue.level === 'critical' ? 'hi-item--crit' : 'hi-item--warn'">
                    <strong>{{ issue.label }}</strong>
                    <span v-if="issue.detail" class="hi-detail">{{ issue.detail }}</span>
                  </li>
                </ul>
                <!-- Still loading component data -->
                <div v-else-if="srv._loading" class="text-muted text-xs" style="padding: 0.25rem 0">
                  Loading component details…
                </div>
                <!-- Data loaded but no specific component issues -->
                <div v-else class="text-xs" style="padding: 0.25rem 0; color: #fcd34d;">
                  No specific sensor/component issues detected. The warning may be from a RAID volume, PSU, or NIC. Check the <button class="hi-tab-link" @click="switchTab(srv, 'hardware')">Hardware</button> and <button class="hi-tab-link" @click="switchTab(srv, 'logs')">Logs</button> tabs.
                </div>

                <!-- System event log entries -->
                <div v-if="srv._logs === null" class="hi-footer text-muted text-xs">
                  Loading system event log…
                </div>
                <template v-else>
                  <div v-if="recentAlertLogs(srv).length" class="hi-footer">
                    <div class="hi-footer-title">Recent Warning / Critical events:</div>
                    <ul class="hi-log-list">
                      <li v-for="e in recentAlertLogs(srv)" :key="e.id"
                          :class="e.severity === 'Critical' ? 'hi-item--crit' : 'hi-item--warn'">
                        <span class="text-xs text-muted" style="white-space:nowrap">{{ formatDate(e.created) }}</span>
                        {{ e.message }}
                      </li>
                    </ul>
                  </div>
                  <!-- No filtered events — show most recent raw entries as fallback -->
                  <div v-else-if="srv._logs.length" class="hi-footer">
                    <div class="hi-footer-title">Most recent event log entries (no Warning/Critical found):</div>
                    <ul class="hi-log-list">
                      <li v-for="e in srv._logs.slice(0, 5)" :key="e.id" style="color:#94a3b8">
                        <span class="text-xs text-muted" style="white-space:nowrap">{{ formatDate(e.created) }}</span>
                        {{ e.message }}
                      </li>
                    </ul>
                  </div>
                  <div v-else class="hi-footer text-muted text-xs">
                    System event log is empty.
                  </div>
                </template>
              </div>
              <!-- ─────────────────────────────────────────────────────── -->

              <div class="details-grid">
                <div class="detail-section">
                  <h4>System Information</h4>
                  <div class="stat-list">
                    <div class="stat-row"><span>Manufacturer</span><span>{{ srv._info.manufacturer }}</span></div>
                    <div class="stat-row"><span>Model</span><span>{{ srv._info.model }}</span></div>
                    <div class="stat-row"><span>Serial</span><span>{{ srv._info.serial_number }}</span></div>
                    <div class="stat-row"><span>BIOS</span><span>{{ srv._info.bios_version }}</span></div>
                    <div class="stat-row"><span>Hostname</span><span>{{ srv._info.hostname }}</span></div>
                    <div class="stat-row"><span>Memory</span><span>{{ srv._info.memory_total_gb }} GB</span></div>
                    <div class="stat-row"><span>CPU</span><span>{{ srv._info.processor_count }}x {{ srv._info.processor_model }}</span></div>
                    <div class="stat-row"><span>BMC IP</span><a :href="`https://${srv.idrac_hostname}:${srv.idrac_port || 443}`" target="_blank" rel="noopener" class="font-mono bmc-link">{{ srv.idrac_hostname }}:{{ srv.idrac_port || 443 }}</a></div>
                    <template v-if="srv._useSSH">
                      <div v-if="srv._info._ssh_os" class="stat-row"><span>OS</span><span>{{ srv._info._ssh_os }}</span></div>
                      <div v-if="srv._info._ssh_kernel" class="stat-row"><span>Kernel</span><span>{{ srv._info._ssh_kernel }}</span></div>
                      <div v-if="srv._info._ssh_uptime" class="stat-row"><span>Uptime</span><span>{{ srv._info._ssh_uptime }}</span></div>
                    </template>
                  </div>
                </div>
                <div v-if="!srv._useSSH" class="detail-section">
                  <h4>Power Control</h4>
                  <div class="power-state-row mb-1">
                    <span :class="['power-badge-lg', srv._info.power_state === 'On' ? 'power-on' : 'power-off']">
                      {{ srv._info.power_state || 'Unknown' }}
                    </span>
                    <span :class="['health-badge-lg', `health-${(srv._info.health || 'unknown').toLowerCase()}`]">
                      {{ srv._info.health || 'Unknown' }}
                    </span>
                  </div>
                  <div class="power-buttons">
                    <button @click="powerAction(srv, 'on')" class="btn btn-success btn-sm" :disabled="srv._actioning">Power On</button>
                    <button @click="powerAction(srv, 'graceful_off')" class="btn btn-warning btn-sm" :disabled="srv._actioning">Graceful Off</button>
                    <button @click="powerAction(srv, 'off')" class="btn btn-danger btn-sm" :disabled="srv._actioning">Force Off</button>
                    <button @click="powerAction(srv, 'graceful_reset')" class="btn btn-outline btn-sm" :disabled="srv._actioning">Graceful Restart</button>
                    <button @click="powerAction(srv, 'reset')" class="btn btn-outline btn-sm" :disabled="srv._actioning">Force Reset</button>
                    <button @click="powerAction(srv, 'power_cycle')" class="btn btn-outline btn-sm" :disabled="srv._actioning" title="Cold power cycle via BMC">Power Cycle</button>
                  </div>
                  <!-- Power history: recent on/off/reset events from SEL -->
                  <div v-if="powerHistory(srv).length" class="power-history mt-2">
                    <div class="power-history__title">Recent Power Events</div>
                    <ul class="power-history__list">
                      <li v-for="ev in powerHistory(srv)" :key="ev.id" class="power-history__item">
                        <span class="text-xs text-muted" style="white-space:nowrap">{{ formatDate(ev.created) }}</span>
                        <span :class="['power-history__badge', powerEventClass(ev)]">{{ ev.severity }}</span>
                        <span class="text-xs">{{ ev.message }}</span>
                      </li>
                    </ul>
                  </div>
                </div>
              </div>
              <div class="charts-row mt-2" v-if="srv._thermal || srv._powerUsage">
                <div class="chart-section" v-if="srv._thermal?.temperatures?.length">
                  <h4>Temperatures ({{ tempLabel }})</h4>
                  <div class="chart-wrapper">
                    <Bar :data="tempChartData(srv._thermal)" :options="tempChartOptions" />
                  </div>
                </div>
                <div class="chart-section" v-if="srv._thermal?.fans?.length">
                  <h4>Fan Speeds (RPM)</h4>
                  <div class="chart-wrapper">
                    <Bar :data="fanChartData(srv._thermal)" :options="fanChartOptions" />
                  </div>
                </div>
                <div class="chart-section chart-section--sm" v-if="srv._powerUsage?.power_control?.length">
                  <h4>Power Usage (W)</h4>
                  <div class="chart-wrapper chart-wrapper--sm">
                    <Doughnut :data="powerChartData(srv._powerUsage)" :options="powerChartOptions" />
                  </div>
                  <div class="power-label text-center text-sm mt-1">
                    {{ srv._powerUsage.power_control[0]?.consumed_watts }}W
                    <span class="text-muted" v-if="srv._powerUsage.power_control[0]?.capacity_watts">
                      / {{ srv._powerUsage.power_control[0].capacity_watts }}W
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <!-- TAB: Hardware -->
            <div v-if="srv._info && srv._activeTab === 'hardware'">
              <div v-if="srv._hwLoading" class="details-loading">
                <div class="loading-spinner"></div><span class="text-muted text-sm">Loading hardware info…</span>
              </div>
              <div v-else-if="srv._hardware">
                <!-- Processors -->
                <div class="detail-section mb-2" v-if="srv._hardware.processors.length">
                  <h4>Processors ({{ srv._hardware.processors.length }})</h4>
                  <div class="hw-table-wrapper">
                    <table class="table">
                      <thead><tr><th>Socket</th><th>Model</th><th>Cores/Threads</th><th>Speed</th><th>Health</th></tr></thead>
                      <tbody>
                        <tr v-for="p in srv._hardware.processors" :key="p.id">
                          <td class="text-xs">{{ p.socket }}</td>
                          <td class="text-xs">{{ p.model }}</td>
                          <td class="text-xs">{{ p.cores }}C / {{ p.threads }}T</td>
                          <td class="text-xs">{{ p.speed_mhz ? (p.speed_mhz/1000).toFixed(1)+'GHz' : '—' }}</td>
                          <td class="text-xs"><span :class="['health-badge', `health-${(p.health||'unknown').toLowerCase()}`]">{{ p.health || '—' }}</span></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
                <!-- Memory -->
                <div class="detail-section mb-2" v-if="srv._hardware.modules.length">
                  <h4>Memory ({{ srv._hardware.modules.length }} DIMMs — {{ srv._hardware.modules.reduce((s,m)=>s+(m.capacity_mib||0),0)/1024 }}GB total)</h4>
                  <div class="hw-table-wrapper">
                    <table class="table">
                      <thead><tr><th>Slot</th><th>Manufacturer</th><th>Capacity</th><th>Speed</th><th>Type</th><th>Health</th></tr></thead>
                      <tbody>
                        <tr v-for="m in srv._hardware.modules" :key="m.id">
                          <td class="text-xs">{{ m.id }}</td>
                          <td class="text-xs">{{ m.manufacturer }}</td>
                          <td class="text-xs">{{ m.capacity_mib ? (m.capacity_mib/1024).toFixed(0)+'GB' : '—' }}</td>
                          <td class="text-xs">{{ m.speed_mhz ? m.speed_mhz+'MHz' : '—' }}</td>
                          <td class="text-xs">{{ m.type }}</td>
                          <td class="text-xs"><span :class="['health-badge', `health-${(m.health||'unknown').toLowerCase()}`]">{{ m.health || '—' }}</span></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
                <!-- Storage -->
                <div v-for="ctrl in srv._hardware.controllers" :key="ctrl.id" class="detail-section mb-2">
                  <h4>Storage: {{ ctrl.name || ctrl.model }} <span :class="['health-badge', `health-${(ctrl.health||'unknown').toLowerCase()}`]">{{ ctrl.health }}</span></h4>
                  <div v-if="ctrl.drives.length" class="hw-table-wrapper">
                    <table class="table">
                      <thead><tr><th>Drive</th><th>Model</th><th>Serial</th><th>Size</th><th>Type</th><th>RPM</th><th>Health</th></tr></thead>
                      <tbody>
                        <tr v-for="d in ctrl.drives" :key="d.id">
                          <td class="text-xs">{{ d.name }}</td>
                          <td class="text-xs">{{ d.model }}</td>
                          <td class="text-xs font-mono">{{ d.serial }}</td>
                          <td class="text-xs">{{ d.capacity_gb ? d.capacity_gb+'GB' : '—' }}</td>
                          <td class="text-xs">{{ d.media_type }} / {{ d.protocol }}</td>
                          <td class="text-xs">{{ d.rpm ? d.rpm.toLocaleString() : '—' }}</td>
                          <td class="text-xs"><span :class="['health-badge', `health-${(d.health||'unknown').toLowerCase()}`]">{{ d.health || d.state }}</span></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <div v-else class="text-muted text-xs">No drives detected</div>
                </div>
                <div v-if="!srv._hardware.processors.length && !srv._hardware.modules.length && !srv._hardware.controllers.length" class="text-muted text-sm">No hardware data available</div>
              </div>
            </div>

            <!-- TAB: Sensors -->
            <div v-if="srv._info && srv._activeTab === 'sensors'">
              <div v-if="srv._sensorsLoading" class="details-loading">
                <div class="loading-spinner"></div><span class="text-muted text-sm">Fetching sensor readings…</span>
              </div>
              <div v-else-if="srv._useSSH && !srv._redfishOK" class="text-muted text-sm p-2">
                Sensor readings are not available in SSH-only mode. Configure Redfish (iDRAC/iLO) credentials to enable.
              </div>
              <div v-else-if="srv._sensors">
                <div class="flex gap-1 mb-1" style="align-items:center">
                  <span class="text-muted text-xs">{{ (srv._sensors.sensors || []).length }} sensors</span>
                  <div style="margin-left:auto">
                    <button @click="loadSensors(srv)" class="btn btn-outline btn-sm">Refresh</button>
                  </div>
                </div>
                <div v-if="!srv._sensors.sensors || srv._sensors.sensors.length === 0" class="text-muted text-sm">
                  No sensor data available from this BMC.
                </div>
                <div v-else class="hw-table-wrapper">
                  <table class="table">
                    <thead>
                      <tr>
                        <th>Sensor Name</th>
                        <th>Type</th>
                        <th>Reading</th>
                        <th>Warning Threshold</th>
                        <th>Critical Threshold</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="sensor in srv._sensors.sensors" :key="sensor.name + sensor.type"
                          :class="sensor.status === 'Critical' ? 'row-critical' : sensor.status === 'Warning' ? 'row-warning' : ''">
                        <td class="text-xs font-bold">{{ sensor.name }}</td>
                        <td class="text-xs">
                          <span :class="['sensor-type-pill', `sensor-type--${(sensor.type || '').toLowerCase().replace(/\s+/g,'_')}`]">
                            {{ sensor.type }}
                          </span>
                        </td>
                        <td class="text-xs font-mono">
                          {{ sensor.reading != null ? sensor.reading + ' ' + sensor.unit : '—' }}
                        </td>
                        <td class="text-xs text-muted font-mono">
                          {{ sensor.upper_warning != null ? sensor.upper_warning + ' ' + sensor.unit : '—' }}
                        </td>
                        <td class="text-xs text-muted font-mono">
                          {{ sensor.upper_critical != null ? sensor.upper_critical + ' ' + sensor.unit : '—' }}
                        </td>
                        <td class="text-xs">
                          <span :class="['health-badge', `health-${(sensor.status || 'unknown').toLowerCase()}`]">
                            {{ sensor.status || 'Unknown' }}
                          </span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
              <div v-else class="text-muted text-sm">
                Sensor data not loaded.
                <button @click="loadSensors(srv)" class="btn btn-outline btn-sm ml-1">Load Sensors</button>
              </div>
            </div>

            <!-- TAB: Network -->
            <div v-if="srv._info && srv._activeTab === 'network'">
              <div v-if="srv._netLoading" class="details-loading">
                <div class="loading-spinner"></div><span class="text-muted text-sm">Loading network info…</span>
              </div>
              <div v-else-if="srv._network">
                <!-- BMC manager info banner -->
                <div v-if="srv._manager" class="manager-banner mb-2">
                  <span class="text-xs text-muted">{{ srv._manager.name }}</span>
                  <span class="text-xs ml-1">Firmware: <strong>{{ srv._manager.firmware_version }}</strong></span>
                  <span :class="['health-badge', `health-${(srv._manager.health||'unknown').toLowerCase()}`, 'ml-1']">{{ srv._manager.health }}</span>
                </div>

                <!-- Network interface edit form -->
                <div v-if="netEditForm && netEditForm._srv === srv" class="net-edit-form mb-2">
                  <h4>Edit Interface: {{ netEditForm._ifaceId }}</h4>
                  <div class="form-row">
                    <label class="form-label">
                      <input type="checkbox" v-model="netEditForm.dhcp" /> DHCP Enabled
                    </label>
                  </div>
                  <template v-if="!netEditForm.dhcp">
                    <div class="form-row-grid">
                      <div class="form-group"><label class="form-label">IP Address</label><input v-model="netEditForm.address" class="form-control form-control-sm" placeholder="192.168.1.100" /></div>
                      <div class="form-group"><label class="form-label">Subnet Mask</label><input v-model="netEditForm.prefix" class="form-control form-control-sm" placeholder="255.255.255.0" /></div>
                      <div class="form-group"><label class="form-label">Gateway</label><input v-model="netEditForm.gateway" class="form-control form-control-sm" placeholder="192.168.1.1" /></div>
                    </div>
                  </template>
                  <div class="form-row-grid">
                    <div class="form-group"><label class="form-label">DNS 1</label><input v-model="netEditForm.dns1" class="form-control form-control-sm" placeholder="8.8.8.8" /></div>
                    <div class="form-group"><label class="form-label">DNS 2</label><input v-model="netEditForm.dns2" class="form-control form-control-sm" placeholder="8.8.4.4" /></div>
                  </div>
                  <div class="flex gap-1 mt-1">
                    <button @click="cancelNetEdit()" class="btn btn-outline btn-sm">Cancel</button>
                    <button @click="saveNetwork()" class="btn btn-primary btn-sm" :disabled="netSaving">{{ netSaving ? 'Saving…' : 'Save Changes' }}</button>
                  </div>
                </div>

                <!-- Interface list -->
                <div v-for="iface in srv._network.interfaces" :key="iface.id" class="net-iface-card mb-2">
                  <div class="net-iface-header">
                    <div>
                      <strong class="text-sm">{{ iface.name || iface.id }}</strong>
                      <span class="text-xs text-muted ml-1">{{ iface.mac_address }}</span>
                      <span :class="['power-badge', iface.link_status === 'LinkUp' ? 'power-on' : 'power-off', 'ml-1']">{{ iface.link_status || 'Unknown' }}</span>
                      <span v-if="iface.dhcp_enabled" class="type-pill type-pill--standalone ml-1">DHCP</span>
                      <span v-else class="type-pill type-pill--pve ml-1">Static</span>
                    </div>
                    <button @click="startNetEdit(srv, iface)" class="btn btn-outline btn-sm" v-if="!srv._useSSH && (!netEditForm || netEditForm._ifaceId !== iface.id)">Edit</button>
                  </div>
                  <div class="stat-list mt-1">
                    <div v-for="addr in iface.ipv4" :key="addr.Address" class="stat-row">
                      <span>IPv4</span><span class="font-mono">{{ addr.Address }} / {{ addr.SubnetMask }} → {{ addr.Gateway }}</span>
                    </div>
                    <div v-for="addr in iface.ipv6" :key="addr.Address" class="stat-row">
                      <span>IPv6</span><span class="font-mono text-xs">{{ addr.Address }}</span>
                    </div>
                    <div v-if="iface.speed_mbps" class="stat-row"><span>Speed</span><span>{{ iface.speed_mbps }} Mbps</span></div>
                    <div v-if="iface.fqdn" class="stat-row"><span>FQDN</span><span>{{ iface.fqdn }}</span></div>
                    <div v-if="iface.name_servers?.length" class="stat-row"><span>DNS</span><span>{{ iface.name_servers.join(', ') }}</span></div>
                  </div>
                </div>
                <div v-if="!srv._network.interfaces?.length" class="text-muted text-sm">No network interfaces found</div>
              </div>
            </div>

            <!-- TAB: Firmware -->
            <div v-if="srv._info && srv._activeTab === 'firmware'">
              <div v-if="srv._fwLoading" class="details-loading">
                <div class="loading-spinner"></div><span class="text-muted text-sm">Loading firmware inventory…</span>
              </div>
              <div v-else-if="srv._firmware">
                <div class="flex gap-1 mb-1" style="align-items:center">
                  <span class="text-muted text-xs">{{ srv._firmware.firmware?.length || 0 }} components</span>
                  <span v-if="srv._firmware.source === 'ssh'" class="type-pill type-pill--pbs text-xs">via SSH</span>
                  <div style="margin-left:auto;display:flex;gap:0.4rem">
                    <button v-if="srv._useSSH" @click="runUpdate(srv)" class="btn btn-warning btn-sm" :disabled="updateRunning">
                      {{ updateRunning ? 'Updating…' : 'Apply Updates' }}
                    </button>
                    <button @click="loadFirmware(srv)" class="btn btn-outline btn-sm">Refresh</button>
                  </div>
                </div>
                <div class="hw-table-wrapper">
                  <table class="table">
                    <thead><tr><th>Component</th><th>Version</th><th>Release Date</th><th>Updateable</th><th>Health</th></tr></thead>
                    <tbody>
                      <tr v-for="fw in srv._firmware.firmware" :key="fw.id">
                        <td class="text-xs">{{ fw.name }}</td>
                        <td class="text-xs font-mono">{{ fw.version }}</td>
                        <td class="text-xs">{{ fw.release_date ? new Date(fw.release_date).toLocaleDateString() : '—' }}</td>
                        <td class="text-xs">{{ fw.updateable ? '✓' : '—' }}</td>
                        <td class="text-xs"><span v-if="fw.health" :class="['health-badge', `health-${fw.health.toLowerCase()}`]">{{ fw.health }}</span></td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            <!-- TAB: Logs -->
            <div v-if="srv._info && srv._activeTab === 'logs'">
              <div class="flex gap-1 mb-1" style="align-items:center">
                <h4 style="margin:0">{{ srv._useSSH ? 'System Journal' : 'System Event Log' }}</h4>
                <button @click="loadLogs(srv)" class="btn btn-outline btn-sm">Refresh</button>
              </div>
              <div v-if="srv._logs !== null" class="log-table-wrapper">
                <table class="table">
                  <thead><tr><th>Time</th><th>Severity</th><th>Message</th></tr></thead>
                  <tbody>
                    <tr v-for="entry in srv._logs" :key="entry.id"
                        :class="entry.severity === 'Critical' ? 'row-critical' : entry.severity === 'Warning' ? 'row-warning' : ''">
                      <td class="text-xs text-nowrap">{{ formatDate(entry.created) }}</td>
                      <td class="text-xs">{{ entry.severity }}</td>
                      <td class="text-xs">{{ entry.message }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div v-else class="details-loading">
                <div class="loading-spinner"></div><span class="text-muted text-sm">Loading logs…</span>
              </div>
            </div>

          </div><!-- end details-panel -->
        </div>
      </template>

      <!-- Empty state -->
      <div v-if="allServers.length === 0" class="card text-center p-3 text-muted">
        <p>No servers configured. Add a Proxmox host in <router-link to="/proxmox">Proxmox Hosts</router-link>,
          add a PBS server in <router-link to="/idrac">iDRAC/iLO</router-link>, or add a Standalone BMC above.</p>
      </div>
    </div>

    <!-- ── BMC Config Modal (for PVE / PBS) ── -->
    <div v-if="showBMCModal" class="modal-overlay" @click.self="showBMCModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>Edit — {{ bmcForm._origName }}</h3>
          <button class="modal-close" @click="showBMCModal = false">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">Display Name</label>
            <input v-model="bmcForm.name" class="form-control" placeholder="Name shown in the interface" />
          </div>
          <hr style="border:none;border-top:1px solid var(--border-color);margin:0.75rem 0" />
          <div class="form-group">
            <label class="form-label">BMC Type</label>
            <select v-model="bmcForm.idrac_type" class="form-control">
              <option value="idrac">Dell iDRAC</option>
              <option value="ilo">HPE iLO</option>
              <option value="ipmi">Generic IPMI</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">BMC Hostname / IP</label>
            <input v-model="bmcForm.idrac_hostname" class="form-control" placeholder="192.168.1.200" />
          </div>
          <div class="form-group">
            <label class="form-label">Port</label>
            <input v-model.number="bmcForm.idrac_port" type="number" class="form-control" placeholder="443" />
          </div>
          <div class="form-group">
            <label class="form-label">Username</label>
            <input v-model="bmcForm.idrac_username" class="form-control" placeholder="root" />
          </div>
          <div class="form-group">
            <label class="form-label">Password</label>
            <input v-model="bmcForm.idrac_password" type="password" class="form-control" placeholder="Leave blank to keep existing" />
          </div>
          <div class="form-group">
            <label class="form-label d-flex" style="align-items:center;gap:0.5rem;cursor:pointer">
              <input type="checkbox" v-model="bmcForm.idrac_use_ssh" />
              Use SSH instead of HTTPS (Redfish)
            </label>
            <p class="text-muted text-xs mt-1" style="margin:0">When enabled, hardware and network data comes from SSH using these credentials.</p>
          </div>
        </div>
        <div class="modal-footer" style="justify-content:space-between">
          <button @click="clearBMC()" class="btn btn-danger" :disabled="bmcSaving" title="Remove all BMC credentials from this server">Clear BMC Config</button>
          <div class="flex gap-1">
            <button @click="showBMCModal = false" class="btn btn-outline">Cancel</button>
            <button @click="saveBMC()" class="btn btn-primary" :disabled="bmcSaving">{{ bmcSaving ? 'Saving…' : 'Save' }}</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Add/Edit Standalone BMC Modal ── -->
    <div v-if="showStandaloneModal" class="modal-overlay" @click.self="showStandaloneModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>{{ standaloneForm.id ? 'Edit Standalone BMC' : 'Add Standalone BMC' }}</h3>
          <button class="modal-close" @click="showStandaloneModal = false">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">Name *</label>
            <input v-model="standaloneForm.name" class="form-control" placeholder="Dell PowerEdge R740 — Rack 3" />
          </div>
          <div class="form-group">
            <label class="form-label">Description</label>
            <input v-model="standaloneForm.description" class="form-control" placeholder="Optional description" />
          </div>
          <div class="form-group">
            <label class="form-label">BMC Type</label>
            <select v-model="standaloneForm.idrac_type" class="form-control">
              <option value="idrac">Dell iDRAC</option>
              <option value="ilo">HPE iLO</option>
              <option value="ipmi">Generic IPMI</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">BMC Hostname / IP *</label>
            <input v-model="standaloneForm.idrac_hostname" class="form-control" placeholder="192.168.1.200" />
          </div>
          <div class="form-group">
            <label class="form-label">Port</label>
            <input v-model.number="standaloneForm.idrac_port" type="number" class="form-control" placeholder="443" />
          </div>
          <div class="form-group">
            <label class="form-label">Username *</label>
            <input v-model="standaloneForm.idrac_username" class="form-control" placeholder="root" />
          </div>
          <div class="form-group">
            <label class="form-label">Password *</label>
            <input v-model="standaloneForm.idrac_password" type="password" class="form-control"
                   :placeholder="standaloneForm.id ? 'Leave blank to keep existing' : 'Password'" />
          </div>
          <div class="form-group">
            <label class="form-label d-flex" style="align-items:center;gap:0.5rem;cursor:pointer">
              <input type="checkbox" v-model="standaloneForm.idrac_use_ssh" />
              Use SSH instead of HTTPS (Redfish)
            </label>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="showStandaloneModal = false" class="btn btn-outline">Cancel</button>
          <button @click="saveStandalone()" class="btn btn-primary" :disabled="standaloneSaving">{{ standaloneSaving ? 'Saving…' : 'Save' }}</button>
        </div>
      </div>
    </div>

    <!-- ── SSH Update Output Modal ── -->
    <div v-if="showUpdateModal" class="modal-overlay" @click.self="!updateRunning && (showUpdateModal = false)">
      <div class="modal-content" style="max-width:700px">
        <div class="modal-header">
          <h3>{{ updateRunning ? 'Applying Updates…' : (updateSuccess ? 'Updates Applied' : 'Update Failed') }}</h3>
          <button v-if="!updateRunning" class="modal-close" @click="showUpdateModal = false">×</button>
        </div>
        <div class="modal-body" style="padding:0">
          <pre class="update-output">{{ updateOutput || 'Running…' }}</pre>
        </div>
        <div v-if="!updateRunning" class="modal-footer">
          <span v-if="updateSuccess" class="text-xs" style="color:#16a34a">✓ Completed successfully</span>
          <span v-else class="text-xs" style="color:#dc2626">✗ Completed with errors</span>
          <button @click="showUpdateModal = false" class="btn btn-outline">Close</button>
        </div>
      </div>
    </div>

    <!-- ── PBS Add/Edit Modal ── -->
    <div v-if="showPBSModal" class="modal-overlay" @click.self="showPBSModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>{{ pbsForm.id ? 'Edit Server' : 'Add Other Server' }}</h3>
          <button class="modal-close" @click="showPBSModal = false">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">Name *</label>
            <input v-model="pbsForm.name" class="form-control" placeholder="pbs-primary" />
          </div>
          <div class="form-group">
            <label class="form-label">Hostname / IP *</label>
            <input v-model="pbsForm.hostname" class="form-control" placeholder="pbs.example.com" />
          </div>
          <div class="form-group">
            <label class="form-label">Port</label>
            <input v-model.number="pbsForm.port" type="number" class="form-control" placeholder="8007" />
          </div>
          <div class="form-group">
            <label class="form-label">Username *</label>
            <input v-model="pbsForm.username" class="form-control" placeholder="root@pam" />
          </div>
          <div class="form-group">
            <label class="form-label">Password</label>
            <input v-model="pbsForm.password" type="password" class="form-control"
                   :placeholder="pbsForm.id ? 'Leave blank to keep existing' : 'Password'" />
          </div>
          <div class="form-group">
            <label class="form-label">API Token ID (optional)</label>
            <input v-model="pbsForm.api_token_id" class="form-control" placeholder="root@pam!mytoken" />
          </div>
        </div>
        <div class="modal-footer">
          <button @click="showPBSModal = false" class="btn btn-outline">Cancel</button>
          <button @click="savePBS()" class="btn btn-primary" :disabled="pbsSaving">{{ pbsSaving ? 'Saving…' : 'Save' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Bar, Doughnut } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, ArcElement,
  Tooltip, Legend, Title
} from 'chart.js'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

ChartJS.register(CategoryScale, LinearScale, BarElement, ArcElement, Tooltip, Legend, Title)

export default {
  name: 'IDracManagement',
  components: { Bar, Doughnut },
  setup() {
    const toast = useToast()
    const loading = ref(true)

    // ── Temperature unit (C/F) ──
    const tempUnit = ref(localStorage.getItem('depl0y_temp_unit') || 'C')
    const toDisplay = (c) => {
      if (c == null) return null
      return tempUnit.value === 'F' ? Math.round(c * 9 / 5 + 32) : c
    }
    const tempLabel = computed(() => tempUnit.value === 'F' ? '°F' : '°C')
    const polling = ref(false)

    const allProxmox = ref([])
    const allPBS = ref([])
    const allStandalone = ref([])
    const allNodes = ref([])
    let _pollInterval = null

    // ── Server wrapping ──
    const wrapServer = (obj, stype) => ({
      ...obj,
      _key: `${stype}-${obj.id}`,
      _stype: stype,
      _status: null,
      _info: null,
      _thermal: null,
      _powerUsage: null,
      _logs: null,   // null = not loaded, [] = loaded but empty
      _loading: false,
      _actioning: false,
      _expanded: false,
      _error: null,
      _activeTab: 'overview',
      _hardware: null,
      _network: null,
      _firmware: null,
      _sensors: null,
      _hwLoading: false,
      _netLoading: false,
      _fwLoading: false,
      _sensorsLoading: false,
      _useSSH: obj.idrac_use_ssh || false,
      _redfishOK: false,
      _sshHardware: null,
    })

    const allServers = computed(() => [
      ...allNodes.value,
      ...allPBS.value,
      ...allStandalone.value,
    ])

    const typeLabel = (stype) => ({ pve: 'PVE', pbs: 'PBS', standalone: 'BMC', pve_node: 'Node' })[stype] || stype.toUpperCase()
    const bmcTypeLabel = (t) => ({ idrac: 'iDRAC', ilo: 'iLO', ipmi: 'IPMI' })[t] || (t || 'BMC').toUpperCase()

    // ── Dashboard computed ──
    const dash = computed(() => {
      const servers = allServers.value
      return {
        total: servers.length,
        on: servers.filter(s => s._status?.power_state === 'On').length,
        healthy: servers.filter(s => s._status?.health === 'OK' && !s._status?.error).length,
        warning: servers.filter(s => s._status?.health === 'Warning').length,
        critical: servers.filter(s => s._status?.health === 'Critical').length,
        unreachable: servers.filter(s => s._status?.error && !s._useSSH).length,
        sshMode: servers.filter(s => s._useSSH).length,
        unconfigured: servers.filter(s => !s.idrac_hostname && s._stype !== 'standalone' && !s._useSSH).length,
      }
    })

    const alertedServers = computed(() =>
      allServers.value.filter(s => {
        if (s._status?.health === 'Critical') return true
        if (s._status?.error && !s._useSSH) return true
        if (s._status?.health === 'Warning') return true
        return false
      })
    )

    const alertLevel = (srv) => {
      if (srv._status?.health === 'Critical' || (srv._status?.error && !srv._useSSH)) return 'crit'
      if (srv._status?.health === 'Warning') return 'warn'
      return ''
    }

    const alertReason = (srv) => {
      if (srv._status?.error && !srv._useSSH) return 'Unreachable'
      if (srv._status?.health === 'Critical') return 'Critical'
      if (srv._status?.health === 'Warning') return 'Warning'
      return ''
    }

    /** Build a list of specific issues for the health issues panel in Overview. */
    const healthIssues = (srv) => {
      const issues = []
      const health = srv._info?.health || srv._status?.health
      if (!health || health === 'OK' || health === 'Unknown') return issues

      // BMC unreachable
      if (srv._status?.error && !srv._useSSH) {
        issues.push({ level: 'critical', label: 'BMC Unreachable', detail: srv._status.error })
        return issues
      }

      // Temperature sensors over or near threshold
      const temps = srv._thermal?.temperatures || []
      for (const t of temps) {
        if (t.health && t.health !== 'OK') {
          const crit = t.upper_threshold_critical ? ` (threshold: ${toDisplay(t.upper_threshold_critical)}${tempLabel.value})` : ''
          issues.push({
            level: t.health.toLowerCase() === 'critical' ? 'critical' : 'warn',
            label: `High temperature: ${t.name}`,
            detail: `${toDisplay(t.reading_celsius)}${tempLabel.value}${crit}`,
          })
        }
      }

      // Fan health
      const fans = srv._thermal?.fans || []
      for (const f of fans) {
        if (f.health && f.health !== 'OK') {
          issues.push({
            level: f.health.toLowerCase() === 'critical' ? 'critical' : 'warn',
            label: `Fan issue: ${f.name}`,
            detail: f.reading_rpm != null ? `${f.reading_rpm} RPM` : '',
          })
        }
      }

      // Processor health
      for (const p of srv._hardware?.processors || []) {
        if (p.health && p.health !== 'OK') {
          issues.push({ level: 'critical', label: `CPU issue: ${p.socket || p.id}`, detail: p.model })
        }
      }

      // Memory health
      for (const m of srv._hardware?.modules || []) {
        if (m.health && m.health !== 'OK') {
          issues.push({ level: 'critical', label: `Memory issue: ${m.id}`, detail: m.manufacturer })
        }
      }

      // Drive health
      for (const ctrl of srv._hardware?.controllers || []) {
        for (const d of ctrl.drives || []) {
          if (d.health && d.health !== 'OK') {
            issues.push({ level: 'critical', label: `Drive issue: ${d.name || d.id}`, detail: `${d.model} ${d.capacity_gb ? d.capacity_gb + ' GB' : ''}`.trim() })
          }
        }
      }

      return issues
    }

    /** Return recent Warning/Critical SEL entries for the health issues panel. */
    const recentAlertLogs = (srv) => {
      if (!Array.isArray(srv._logs)) return []
      return srv._logs
        .filter(e => e.severity === 'Critical' || e.severity === 'Warning')
        .slice(0, 5)
    }

    /**
     * Return recent power-related SEL entries for the Power History strip.
     * Filters for keywords like "Power", "Reset", "Startup", "Shutdown", "Boot".
     */
    const _POWER_KEYWORDS = /power|reset|startup|shutdown|boot|ac lost|button|chassis intrusion/i
    const powerHistory = (srv) => {
      if (!Array.isArray(srv._logs)) return []
      return srv._logs
        .filter(e => _POWER_KEYWORDS.test(e.message || '') || _POWER_KEYWORDS.test(e.sensor_type || ''))
        .slice(0, 8)
    }

    const powerEventClass = (ev) => {
      if (ev.severity === 'Critical') return 'power-event--crit'
      if (ev.severity === 'Warning') return 'power-event--warn'
      return 'power-event--info'
    }

    // ── Dashboard charts ──
    const healthChartData = computed(() => {
      const counts = { OK: 0, Warning: 0, Critical: 0, Unknown: 0 }
      for (const s of allServers.value) {
        const h = s._status?.health
        if (h === 'OK') counts.OK++
        else if (h === 'Warning') counts.Warning++
        else if (h === 'Critical') counts.Critical++
        else counts.Unknown++
      }
      return {
        labels: ['Healthy', 'Warning', 'Critical', 'Unknown'],
        datasets: [{
          data: [counts.OK, counts.Warning, counts.Critical, counts.Unknown],
          backgroundColor: ['#16a34a', '#d97706', '#dc2626', '#94a3b8'],
          borderWidth: 0,
        }]
      }
    })

    const powerStateChartData = computed(() => {
      let on = 0, off = 0, unknown = 0
      for (const s of allServers.value) {
        const p = s._status?.power_state
        if (p === 'On') on++
        else if (p === 'Off') off++
        else unknown++
      }
      return {
        labels: ['On', 'Off', 'Unknown'],
        datasets: [{
          data: [on, off, unknown],
          backgroundColor: ['#16a34a', '#dc2626', '#94a3b8'],
          borderWidth: 0,
        }]
      }
    })

    const tempBarData = computed(() => {
      const servers = allServers.value.filter(s => s._status?.max_temp_c != null)
      return {
        labels: servers.map(s => s.name),
        datasets: [{
          label: tempLabel.value,
          data: servers.map(s => toDisplay(s._status.max_temp_c)),
          backgroundColor: servers.map(s =>
            s._status.max_temp_c >= 75 ? 'rgba(220,38,38,0.8)'
            : s._status.max_temp_c >= 55 ? 'rgba(217,119,6,0.8)'
            : 'rgba(37,99,235,0.7)'
          ),
          borderRadius: 4,
        }]
      }
    })

    const dashChartOptions = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom', labels: { font: { size: 10 }, boxWidth: 12 } } },
      cutout: '60%',
    }

    const tempBarOptions = computed(() => ({
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => `${ctx.raw}${tempLabel.value}` } } },
      scales: {
        y: { min: 0, ticks: { font: { size: 10 }, callback: v => `${v}${tempLabel.value}` } },
        x: { ticks: { font: { size: 9 }, maxRotation: 30 } }
      }
    }))

    // ── Load lists ──
    const loadAll = async () => {
      loading.value = true
      try {
        const [pbsRes, saRes, nodesRes, statusRes] = await Promise.all([
          api.pbs.list(),
          api.idrac.listStandalone(),
          api.idrac.listNodes().catch(() => ({ data: [] })),
          api.idrac.getStatus().catch(() => ({ data: {} })),
        ])
        allPBS.value = pbsRes.data.map(s => wrapServer(s, 'pbs'))
        allStandalone.value = saRes.data.map(b => wrapServer(b, 'standalone'))
        allNodes.value = nodesRes.data.map(n => wrapServer(n, 'pve_node'))

        applyStatusCache(statusRes.data)
      } catch (e) {
        toast.error('Failed to load server list')
      } finally {
        loading.value = false
      }
    }

    const applyStatusCache = (cache) => {
      for (const srv of allServers.value) {
        const key = `${srv._stype}:${srv.id}`
        if (cache[key]) srv._status = cache[key]
      }
    }

    // ── Poll status every 2 min ──
    const pollNow = async () => {
      polling.value = true
      try {
        // triggerPoll runs run_bmc_poll() server-side and returns the updated cache
        const res = await api.idrac.triggerPoll()
        applyStatusCache(res.data)
        // Re-fetch detail data for expanded servers
        for (const srv of allServers.value) {
          if (srv._expanded) loadServerDetail(srv)
        }
      } catch (e) {
        toast.error('Poll failed')
      } finally {
        polling.value = false
      }
    }

    // ── Expand / collapse ──
    const expandServer = (srv) => {
      if (srv._useSSH) {
        // SSH mode: just need credentials, not BMC reachability
        if (!srv.idrac_username) {
          toast.warning('No SSH credentials configured — set them in "Edit BMC"')
          return
        }
      } else {
        if (!srv.idrac_hostname && srv._stype !== 'standalone') {
          toast.warning('No BMC configured for this server')
          return
        }
        // Only block on BMC error in Redfish mode
        if (srv._status?.error && !srv._info) {
          srv._expanded = true
          srv._error = `BMC unreachable: ${srv._status.error}`
          return
        }
      }
      srv._expanded = true
      // For Redfish servers: pre-populate from status cache so tabs appear immediately
      // For SSH servers: skip pre-populate — SSH fetches full data from scratch,
      // and pre-populating causes Vue reactivity to miss the _info replacement
      if (srv._status && !srv._info && !srv._useSSH) {
        srv._info = {
          power_state: srv._status.power_state,
          health: srv._status.health,
          model: srv._status.model || '',
          manufacturer: '', serial_number: '', bios_version: '',
          hostname: '', memory_total_gb: 0, processor_count: null, processor_model: '',
        }
      }
      // Load full details in background — don't await
      loadServerDetail(srv)
    }

    const collapseServer = (srv) => {
      srv._expanded = false
    }

    const jumpToServer = (srv) => {
      expandServer(srv)
      // Always land on Overview — the health issues panel there shows the specific problem.
      srv._activeTab = 'overview'
      // Proactively load logs and hardware so the health panel has component data
      const health = srv._status?.health
      if (health === 'Warning' || health === 'Critical') {
        if (srv._logs === null && !srv._loading) loadLogs(srv)
        if (!srv._hardware && !srv._hwLoading) loadHardware(srv)
      }
      setTimeout(() => {
        const el = document.getElementById(`srv-card-${srv._key}`)
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 50)
    }

    const _populateInfoFromSSH = (srv, data) => {
      srv._sshHardware = data
      srv._redfishOK = false
      const sys = data.system || {}
      const totalMemGb = Math.round((data.modules || []).reduce((s, m) => s + (m.capacity_mib || 0), 0) / 1024 * 10) / 10
      srv._info = {
        manufacturer: sys.manufacturer || '',
        model: sys.model || '',
        serial_number: sys.serial || '',
        bios_version: [sys.bios_version, sys.bios_date].filter(Boolean).join(' — '),
        power_state: 'On',
        health: 'OK',
        processor_count: data.processors?.length || null,
        processor_model: data.processors?.[0]?.model || '',
        memory_total_gb: totalMemGb,
        hostname: srv.hostname || srv.idrac_hostname || '',
        _ssh_kernel: sys.kernel || '',
        _ssh_os: sys.os || '',
        _ssh_uptime: sys.uptime || '',
      }
    }

    const loadServerDetail = async (srv) => {
      srv._loading = true
      srv._error = null
      // For SSH mode, clear any stale _info so Vue detects the null→object
      // transition when SSH data arrives (avoids reactivity miss on object replacement)
      if (srv._useSSH) srv._info = null

      const calls = _apiFns(srv)

      // Always try Redfish first — best source for iDRAC/iLO overview data.
      // SSH mode acts as fallback when Redfish is unavailable.
      const [infoR, thermalR, powerR] = await Promise.allSettled([
        calls.getInfo(),
        calls.getThermal(),
        calls.getPowerUsage(),
      ])

      if (infoR.status === 'fulfilled') {
        srv._info = infoR.value.data
        srv._redfishOK = true
      }
      if (thermalR.status === 'fulfilled') srv._thermal = thermalR.value.data
      if (powerR.status === 'fulfilled') srv._powerUsage = powerR.value.data

      // If Redfish info failed, try SSH as fallback.
      // Use !_redfishOK (not !_info) because expandServer may pre-populate _info from status cache,
      // which would skip SSH even though Redfish never actually ran successfully.
      if (!srv._redfishOK) {
        if (srv._useSSH) {
          try {
            const res = await calls.getSshHardware()
            _populateInfoFromSSH(srv, res.data)
          } catch (e) {
            if (!srv._info) {
              srv._error = e.response?.data?.detail || e.message || 'Redfish and SSH both failed'
            }
          }
        } else if (!srv._info) {
          const err = infoR.reason
          srv._error = err?.response?.data?.detail || err?.message || 'Failed to connect to BMC'
        }
      }

      // Pre-fetch logs: SSH journal if SSH mode and Redfish not working, else Redfish SEL
      if (srv._useSSH && !srv._redfishOK) {
        calls.getSshLogs().then(r => { srv._logs = r.data?.entries ?? [] }).catch(() => { srv._logs = [] })
      } else {
        calls.getLogs().then(r => { srv._logs = r.data?.entries ?? [] }).catch(() => { srv._logs = [] })
      }

      srv._loading = false
    }

    const loadLogs = async (srv) => {
      try {
        // SSH logs only when SSH mode is on AND Redfish isn't working
        const res = (srv._useSSH && !srv._redfishOK)
          ? await _apiFns(srv).getSshLogs()
          : await _apiFns(srv).getLogs()
        srv._logs = res.data.entries
      } catch {
        srv._logs = []
      }
    }

    // ── Tab switching and lazy loading ──
    const switchTab = async (srv, tab) => {
      srv._activeTab = tab
      if (tab === 'hardware' && !srv._hardware && !srv._hwLoading) loadHardware(srv)
      if (tab === 'network' && !srv._network && !srv._netLoading) loadNetwork(srv)
      if (tab === 'firmware' && !srv._firmware && !srv._fwLoading) loadFirmware(srv)
      if (tab === 'sensors' && !srv._sensors && !srv._sensorsLoading) loadSensors(srv)
      if (tab === 'logs' && srv._logs === null) loadLogs(srv)
    }

    const loadSensors = async (srv) => {
      if (srv._useSSH && !srv._redfishOK) return  // SSH-only mode — no Redfish sensors
      srv._sensorsLoading = true
      try {
        const res = await _apiFns(srv).getSensors()
        srv._sensors = res.data
      } catch {
        srv._sensors = { sensors: [] }
      } finally {
        srv._sensorsLoading = false
      }
    }

    const loadHardware = async (srv) => {
      srv._hwLoading = true
      // Use SSH hardware when: SSH mode is on AND Redfish isn't working
      if (srv._useSSH && !srv._redfishOK) {
        if (srv._sshHardware) {
          srv._hardware = {
            processors: srv._sshHardware.processors || [],
            modules: srv._sshHardware.modules || [],
            controllers: srv._sshHardware.controllers || [],
          }
        } else {
          try {
            const res = await _apiFns(srv).getSshHardware()
            srv._sshHardware = res.data
            srv._hardware = {
              processors: res.data.processors || [],
              modules: res.data.modules || [],
              controllers: res.data.controllers || [],
            }
          } catch {
            srv._hardware = { processors: [], modules: [], controllers: [] }
          }
        }
        srv._hwLoading = false
        return
      }
      // Redfish hardware
      const calls = _apiFns(srv)
      const [procRes, memRes, storRes] = await Promise.all([
        calls.getProcessors().catch(() => ({ data: { processors: [] } })),
        calls.getMemory().catch(() => ({ data: { modules: [] } })),
        calls.getStorage().catch(() => ({ data: { controllers: [] } })),
      ])
      srv._hardware = {
        processors: procRes.data.processors || [],
        modules: memRes.data.modules || [],
        controllers: storRes.data.controllers || [],
      }
      srv._hwLoading = false
    }

    const loadNetwork = async (srv) => {
      srv._netLoading = true
      // Use SSH network when: SSH mode is on AND Redfish isn't working
      if (srv._useSSH && !srv._redfishOK) {
        try {
          const res = await _apiFns(srv).getSshNetwork()
          srv._network = res.data
          srv._manager = null
        } catch {
          srv._network = { interfaces: [] }
        }
        srv._netLoading = false
        return
      }
      // Redfish network
      try {
        const [netRes, mgrRes] = await Promise.all([
          _apiFns(srv).getNetwork(),
          _apiFns(srv).getManager().catch(() => ({ data: null })),
        ])
        srv._network = netRes.data
        srv._manager = mgrRes.data
      } catch (e) {
        srv._network = { interfaces: [] }
      }
      srv._netLoading = false
    }

    const loadFirmware = async (srv) => {
      srv._fwLoading = true
      // Use SSH firmware when: SSH mode is on AND Redfish isn't working
      if (srv._useSSH && !srv._redfishOK) {
        try {
          const res = await _apiFns(srv).getSshFirmware()
          srv._firmware = res.data
        } catch {
          srv._firmware = { firmware: [] }
        }
        srv._fwLoading = false
        return
      }
      // Redfish firmware
      try {
        const res = await _apiFns(srv).getFirmware()
        srv._firmware = res.data
      } catch {
        srv._firmware = { firmware: [] }
      }
      srv._fwLoading = false
    }

    // ── Network edit ──
    const netEditForm = ref(null)
    const netSaving = ref(false)

    const startNetEdit = (srv, iface) => {
      const ipv4 = iface.ipv4?.[0] || {}
      netEditForm.value = {
        _srv: srv,
        _ifaceId: iface.id,
        dhcp: iface.dhcp_enabled,
        address: ipv4.Address || '',
        prefix: ipv4.SubnetMask || '',
        gateway: ipv4.Gateway || '',
        dns1: iface.name_servers?.[0] || '',
        dns2: iface.name_servers?.[1] || '',
      }
    }

    const cancelNetEdit = () => { netEditForm.value = null }

    const saveNetwork = async () => {
      netSaving.value = true
      const f = netEditForm.value
      try {
        const payload = {
          DHCPv4: { DHCPEnabled: f.dhcp },
        }
        if (!f.dhcp) {
          payload.IPv4StaticAddresses = [{ Address: f.address, SubnetMask: f.prefix, Gateway: f.gateway }]
        }
        if (f.dns1) payload.NameServers = [f.dns1, f.dns2].filter(Boolean)
        await _apiFns(f._srv).patchNetwork(f._ifaceId, payload)
        toast.success('Network settings saved — changes may require BMC restart')
        // Reload network tab
        f._srv._network = null
        await loadNetwork(f._srv)
        netEditForm.value = null
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Failed to save network settings')
      } finally {
        netSaving.value = false
      }
    }

    // ── API call dispatch by server type ──
    const _apiFns = (srv) => {
      if (srv._stype === 'pve_node') return {
        getInfo: () => api.idrac.getNodeInfo(srv.id),
        getThermal: () => api.idrac.getNodeThermal(srv.id),
        getPowerUsage: () => api.idrac.getNodePowerUsage(srv.id),
        getLogs: () => api.idrac.getNodeLogs(srv.id),
        getSensors: () => api.idrac.getNodeSensors(srv.id),
        test: () => api.idrac.testNode(srv.id),
        testSsh: () => api.idrac.testNodeSsh(srv.id),
        powerAction: (action) => api.idrac.nodepower(srv.id, action),
        getManager: () => api.idrac.getNodeManager(srv.id),
        getNetwork: () => api.idrac.getNodeNetwork(srv.id),
        patchNetwork: (ifaceId, config) => api.idrac.patchNodeNetwork(srv.id, ifaceId, config),
        getProcessors: () => api.idrac.getNodeProcessors(srv.id),
        getMemory: () => api.idrac.getNodeMemory(srv.id),
        getStorage: () => api.idrac.getNodeStorage(srv.id),
        getFirmware: () => api.idrac.getNodeFirmware(srv.id),
        getSshHardware: () => api.idrac.getNodeSshHardware(srv.id),
        getSshNetwork: () => api.idrac.getNodeSshNetwork(srv.id),
        getSshFirmware: () => api.idrac.getNodeSshFirmware(srv.id),
        getSshLogs: () => api.idrac.getNodeSshLogs(srv.id),
        runSshUpdate: () => api.idrac.runNodeSshUpdate(srv.id),
      }
      if (srv._stype === 'pbs') return {
        getInfo: () => api.pbs.getIdracInfo(srv.id),
        getThermal: () => api.pbs.getIdracThermal(srv.id),
        getPowerUsage: () => api.pbs.getIdracPowerUsage(srv.id),
        getLogs: () => api.pbs.getIdracLogs(srv.id),
        getSensors: () => api.pbs.getIdracSensors(srv.id),
        test: () => api.pbs.testIdrac(srv.id),
        testSsh: () => api.pbs.testIdracSsh(srv.id),
        powerAction: (action) => api.pbs.idracPowerAction(srv.id, action),
        getManager: () => api.pbs.getIdracManager(srv.id),
        getNetwork: () => api.pbs.getIdracNetwork(srv.id),
        patchNetwork: (ifaceId, config) => api.pbs.patchIdracNetwork(srv.id, ifaceId, config),
        getProcessors: () => api.pbs.getIdracProcessors(srv.id),
        getMemory: () => api.pbs.getIdracMemory(srv.id),
        getStorage: () => api.pbs.getIdracStorage(srv.id),
        getFirmware: () => api.pbs.getIdracFirmware(srv.id),
        getSshHardware: () => api.pbs.getIdracSshHardware(srv.id),
        getSshNetwork: () => api.pbs.getIdracSshNetwork(srv.id),
        getSshFirmware: () => api.pbs.getIdracSshFirmware(srv.id),
        getSshLogs: () => api.pbs.getIdracSshLogs(srv.id),
        runSshUpdate: () => api.pbs.runIdracSshUpdate(srv.id),
      }
      if (srv._stype === 'standalone') return {
        getInfo: () => api.idrac.getStandaloneInfo(srv.id),
        getThermal: () => api.idrac.getStandaloneThermal(srv.id),
        getPowerUsage: () => api.idrac.getStandalonePowerUsage(srv.id),
        getLogs: () => api.idrac.getStandaloneLogs(srv.id),
        getSensors: () => api.idrac.getStandaloneSensors(srv.id),
        test: () => api.idrac.testStandalone(srv.id),
        testSsh: () => api.idrac.testStandaloneSsh(srv.id),
        powerAction: (action) => api.idrac.standalonepower(srv.id, action),
        getManager: () => api.idrac.getStandaloneManager(srv.id),
        getNetwork: () => api.idrac.getStandaloneNetwork(srv.id),
        patchNetwork: (ifaceId, config) => api.idrac.patchStandaloneNetwork(srv.id, ifaceId, config),
        getProcessors: () => api.idrac.getStandaloneProcessors(srv.id),
        getMemory: () => api.idrac.getStandaloneMemory(srv.id),
        getStorage: () => api.idrac.getStandaloneStorage(srv.id),
        getFirmware: () => api.idrac.getStandaloneFirmware(srv.id),
        getSshHardware: () => api.idrac.getStandaloneSshHardware(srv.id),
        getSshNetwork: () => api.idrac.getStandaloneSshNetwork(srv.id),
        getSshFirmware: () => api.idrac.getStandaloneSshFirmware(srv.id),
        getSshLogs: () => api.idrac.getStandaloneSshLogs(srv.id),
        runSshUpdate: () => api.idrac.runStandaloneSshUpdate(srv.id),
      }
      return {
        getInfo: () => api.idrac.getInfo(srv.id),
        getThermal: () => api.idrac.getThermal(srv.id),
        getPowerUsage: () => api.idrac.getPowerUsage(srv.id),
        getLogs: () => api.idrac.getLogs(srv.id),
        getSensors: () => api.idrac.getSensors(srv.id),
        test: () => api.idrac.testConnection(srv.id),
        testSsh: () => api.idrac.testSsh(srv.id),
        powerAction: (action) => api.idrac.powerAction(srv.id, action),
        getManager: () => api.idrac.getManager(srv.id),
        getNetwork: () => api.idrac.getNetwork(srv.id),
        patchNetwork: (ifaceId, config) => api.idrac.patchNetwork(srv.id, ifaceId, config),
        getProcessors: () => api.idrac.getProcessors(srv.id),
        getMemory: () => api.idrac.getMemory(srv.id),
        getStorage: () => api.idrac.getStorage(srv.id),
        getFirmware: () => api.idrac.getFirmware(srv.id),
        getSshHardware: () => api.idrac.getSshHardware(srv.id),
        getSshNetwork: () => api.idrac.getSshNetwork(srv.id),
        getSshFirmware: () => api.idrac.getSshFirmware(srv.id),
        getSshLogs: () => api.idrac.getSshLogs(srv.id),
        runSshUpdate: () => api.idrac.runSshUpdate(srv.id),
      }
    }

    // ── SSH Update ──
    const showUpdateModal = ref(false)
    const updateOutput = ref('')
    const updateRunning = ref(false)
    const updateSuccess = ref(null)
    let _updateTarget = null

    const runUpdate = async (srv) => {
      if (!confirm(`Apply all pending package updates on ${srv.name}?\n\nThis will run as the configured SSH user and may take several minutes.`)) return
      _updateTarget = srv
      updateOutput.value = ''
      updateSuccess.value = null
      updateRunning.value = true
      showUpdateModal.value = true
      try {
        const res = await _apiFns(srv).runSshUpdate()
        updateOutput.value = res.data.output
        updateSuccess.value = res.data.success
        if (res.data.success) {
          toast.success('Updates applied successfully')
          // Refresh firmware list
          srv._firmware = null
          loadFirmware(srv)
        } else {
          toast.error(`Update failed (exit code ${res.data.exit_code})`)
        }
      } catch (e) {
        updateOutput.value = e.response?.data?.detail || e.message || 'Unknown error'
        updateSuccess.value = false
        toast.error('Update failed')
      } finally {
        updateRunning.value = false
      }
    }

    // ── SSH toggle ──
    const toggleSSH = (srv) => {
      srv._useSSH = !srv._useSSH
      srv._info = null
      srv._hardware = null
      srv._network = null
      srv._firmware = null
      srv._sensors = null
      srv._sshHardware = null
      srv._logs = null
      srv._thermal = null
      srv._powerUsage = null
      srv._error = null
      if (srv._expanded) loadServerDetail(srv)
    }

    const testConnection = async (srv) => {
      try {
        const res = srv._useSSH ? await _apiFns(srv).testSsh() : await _apiFns(srv).test()
        if (res.data.status === 'success') toast.success(res.data.message)
        else toast.error(res.data.message)
      } catch {
        toast.error('Connection failed')
      }
    }

    const powerAction = async (srv, action) => {
      const labels = { on: 'power on', off: 'force power off', graceful_off: 'gracefully shut down', reset: 'force restart', graceful_reset: 'gracefully restart' }
      if (!confirm(`Are you sure you want to ${labels[action] || action} ${srv.name}?`)) return
      srv._actioning = true
      try {
        await _apiFns(srv).powerAction(action)
        toast.success(`Power action '${action}' sent to ${srv.name}`)
        setTimeout(() => loadServerDetail(srv), 3000)
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Power action failed')
      } finally {
        srv._actioning = false
      }
    }

    // ── BMC Config Modal (PVE / PBS) ──
    const showBMCModal = ref(false)
    const bmcSaving = ref(false)
    const bmcForm = ref({})
    let _bmcTarget = null

    const openConfigBMC = (srv) => {
      _bmcTarget = srv
      bmcForm.value = {
        _origName: srv.name,
        _stype: srv._stype,
        name: srv.name,
        idrac_type: srv.idrac_type || 'idrac',
        idrac_hostname: srv.idrac_hostname || '',
        idrac_port: srv.idrac_port || 443,
        idrac_username: srv.idrac_username || '',
        idrac_password: '',
        idrac_use_ssh: srv.idrac_use_ssh || false,
      }
      showBMCModal.value = true
    }

    const saveBMC = async () => {
      bmcSaving.value = true
      try {
        const payload = {
          name: bmcForm.value.name || undefined,
          idrac_type: bmcForm.value.idrac_type,
          idrac_hostname: bmcForm.value.idrac_hostname,
          idrac_port: bmcForm.value.idrac_port,
          idrac_username: bmcForm.value.idrac_username,
          idrac_use_ssh: bmcForm.value.idrac_use_ssh,
        }
        if (bmcForm.value.idrac_password) payload.idrac_password = bmcForm.value.idrac_password

        if (_bmcTarget._stype === 'pbs') {
          const res = await api.pbs.update(_bmcTarget.id, payload)
          Object.assign(_bmcTarget, res.data)
        } else if (_bmcTarget._stype === 'pve_node') {
          await api.proxmox.updateNodeIdrac(_bmcTarget.id, payload)
          // Only update idrac fields — don't overwrite name/node_name
          const { name: _n, ...idracFields } = payload
          Object.assign(_bmcTarget, idracFields)
        } else {
          const res = await api.proxmox.updateHost(_bmcTarget.id, payload)
          Object.assign(_bmcTarget, res.data)
        }
        // Apply SSH toggle immediately without requiring a page reload
        const newSSH = bmcForm.value.idrac_use_ssh || false
        if (_bmcTarget._useSSH !== newSSH) {
          _bmcTarget._useSSH = newSSH
          _bmcTarget._info = null
          _bmcTarget._hardware = null
          _bmcTarget._network = null
          _bmcTarget._firmware = null
          _bmcTarget._sensors = null
          _bmcTarget._sshHardware = null
          _bmcTarget._logs = null
          _bmcTarget._thermal = null
          _bmcTarget._powerUsage = null
        }
        toast.success('Saved')
        showBMCModal.value = false
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Failed to save')
      } finally {
        bmcSaving.value = false
      }
    }

    const clearBMC = async () => {
      if (!confirm(`Remove all BMC credentials from "${_bmcTarget.name}"?`)) return
      bmcSaving.value = true
      try {
        const payload = { idrac_hostname: '', idrac_username: '', idrac_password: '', idrac_type: null, idrac_port: null }
        if (_bmcTarget._stype === 'pbs') {
          const res = await api.pbs.update(_bmcTarget.id, payload)
          Object.assign(_bmcTarget, res.data)
        } else if (_bmcTarget._stype === 'pve_node') {
          await api.proxmox.updateNodeIdrac(_bmcTarget.id, payload)
          // Only clear idrac fields — node stays in the list
          Object.assign(_bmcTarget, payload)
        } else {
          const res = await api.proxmox.updateHost(_bmcTarget.id, payload)
          Object.assign(_bmcTarget, res.data)
        }
        _bmcTarget._status = null
        _bmcTarget._error = null
        _bmcTarget._expanded = false
        toast.success('BMC config cleared')
        showBMCModal.value = false
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Failed to clear BMC config')
      } finally {
        bmcSaving.value = false
      }
    }

    // ── Standalone BMC Modal ──
    const showStandaloneModal = ref(false)
    const standaloneSaving = ref(false)
    const standaloneForm = ref({})

    const openAddStandalone = () => {
      standaloneForm.value = { id: null, name: '', description: '', idrac_type: 'idrac', idrac_hostname: '', idrac_port: 443, idrac_username: 'root', idrac_password: '', idrac_use_ssh: false }
      showStandaloneModal.value = true
    }

    const openEditStandalone = (srv) => {
      standaloneForm.value = { id: srv.id, name: srv.name, description: srv.description || '', idrac_type: srv.idrac_type, idrac_hostname: srv.idrac_hostname, idrac_port: srv.idrac_port, idrac_username: srv.idrac_username, idrac_password: '', idrac_use_ssh: srv.idrac_use_ssh || false }
      showStandaloneModal.value = true
    }

    const saveStandalone = async () => {
      standaloneSaving.value = true
      try {
        const payload = {
          name: standaloneForm.value.name,
          description: standaloneForm.value.description || null,
          idrac_type: standaloneForm.value.idrac_type,
          idrac_hostname: standaloneForm.value.idrac_hostname,
          idrac_port: standaloneForm.value.idrac_port,
          idrac_username: standaloneForm.value.idrac_username,
          idrac_use_ssh: standaloneForm.value.idrac_use_ssh || false,
        }
        if (standaloneForm.value.idrac_password) payload.idrac_password = standaloneForm.value.idrac_password

        if (standaloneForm.value.id) {
          const res = await api.idrac.updateStandalone(standaloneForm.value.id, payload)
          const idx = allStandalone.value.findIndex(s => s.id === standaloneForm.value.id)
          if (idx !== -1) Object.assign(allStandalone.value[idx], res.data)
        } else {
          const res = await api.idrac.createStandalone(payload)
          allStandalone.value.push(wrapServer(res.data, 'standalone'))
        }
        toast.success('Standalone BMC saved')
        showStandaloneModal.value = false
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Failed to save')
      } finally {
        standaloneSaving.value = false
      }
    }

    const deleteStandalone = async (srv) => {
      if (!confirm(`Delete standalone BMC "${srv.name}"?`)) return
      try {
        await api.idrac.deleteStandalone(srv.id)
        allStandalone.value = allStandalone.value.filter(s => s.id !== srv.id)
        toast.success('Deleted')
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Failed to delete')
      }
    }

    const deletePBS = async (srv) => {
      const label = srv.name || srv.hostname || `#${srv.id}`
      if (!confirm(`Delete "${label}" from tracking? This removes it from Depl0y but does not affect the actual server.`)) return
      try {
        await api.pbs.delete(srv.id)
        allPBS.value = allPBS.value.filter(s => s.id !== srv.id)
        toast.success('Removed')
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Failed to delete')
      }
    }

    // ── PBS Modal ──
    const showPBSModal = ref(false)
    const pbsSaving = ref(false)
    const pbsForm = ref({})

    const openAddPBS = () => {
      pbsForm.value = { id: null, name: '', hostname: '', port: 8007, username: 'root@pam', password: '', api_token_id: '' }
      showPBSModal.value = true
    }

    const savePBS = async () => {
      pbsSaving.value = true
      try {
        const payload = { name: pbsForm.value.name, hostname: pbsForm.value.hostname, port: pbsForm.value.port, username: pbsForm.value.username }
        if (pbsForm.value.password) payload.password = pbsForm.value.password
        if (pbsForm.value.api_token_id) payload.api_token_id = pbsForm.value.api_token_id
        if (pbsForm.value.id) {
          const res = await api.pbs.update(pbsForm.value.id, payload)
          const idx = allPBS.value.findIndex(s => s.id === pbsForm.value.id)
          if (idx !== -1) Object.assign(allPBS.value[idx], res.data)
        } else {
          const res = await api.pbs.create(payload)
          allPBS.value.push(wrapServer(res.data, 'pbs'))
        }
        toast.success('PBS server saved')
        showPBSModal.value = false
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Failed to save PBS server')
      } finally {
        pbsSaving.value = false
      }
    }

    // ── Chart data builders ──
    const tempChartData = (thermal) => {
      const temps = thermal.temperatures || []
      const labels = temps.map(t => t.name)
      const values = temps.map(t => toDisplay(t.reading_celsius))
      const bgColors = temps.map(t =>
        t.upper_threshold_critical && t.reading_celsius >= t.upper_threshold_critical - 5
          ? 'rgba(220,38,38,0.75)'
          : t.upper_threshold_critical && t.reading_celsius >= t.upper_threshold_critical - 15
          ? 'rgba(245,158,11,0.75)'
          : 'rgba(37,99,235,0.65)'
      )
      return { labels, datasets: [{ label: tempLabel.value, data: values, backgroundColor: bgColors, borderRadius: 3 }] }
    }

    const fanChartData = (thermal) => {
      const fans = thermal.fans || []
      return {
        labels: fans.map(f => f.name),
        datasets: [{ label: 'RPM', data: fans.map(f => f.reading_rpm), backgroundColor: 'rgba(16,185,129,0.7)', borderRadius: 3 }]
      }
    }

    const powerChartData = (powerUsage) => {
      const ctrl = powerUsage.power_control?.[0]
      if (!ctrl) return { labels: [], datasets: [] }
      const used = ctrl.consumed_watts || 0
      const cap = ctrl.capacity_watts || 0
      const remaining = Math.max(0, cap - used)
      return {
        labels: ['Used', cap ? 'Remaining' : ''],
        datasets: [{
          data: cap ? [used, remaining] : [used],
          backgroundColor: ['rgba(37,99,235,0.8)', 'rgba(226,232,240,0.8)'],
          borderWidth: 0,
        }]
      }
    }

    const tempChartOptions = {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => `${ctx.raw}°C` } } },
      scales: { x: { min: 0, ticks: { font: { size: 10 } } }, y: { ticks: { font: { size: 10 } } } }
    }

    const fanChartOptions = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => `${ctx.raw} RPM` } } },
      scales: { y: { min: 0, ticks: { font: { size: 10 } } }, x: { ticks: { font: { size: 9 }, maxRotation: 30 } } }
    }

    const powerChartOptions = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => `${ctx.raw}W` } } },
      cutout: '65%',
    }

    // ── Formatters ──
    const formatDate = (d) => d ? new Date(d).toLocaleString() : '—'
    const formatRelative = (iso) => {
      if (!iso) return ''
      const diff = Math.round((Date.now() - new Date(iso).getTime()) / 1000)
      if (diff < 10) return 'just now'
      if (diff < 60) return `${diff}s ago`
      if (diff < 3600) return `${Math.round(diff/60)}m ago`
      return `${Math.round(diff/3600)}h ago`
    }

    // Lightweight background refresh: just fetch the cache the scheduler keeps warm
    const _refreshCache = async () => {
      try {
        const res = await api.idrac.getStatus()
        applyStatusCache(res.data)
      } catch { /* silent */ }
    }

    onMounted(async () => {
      await loadAll()
      _pollInterval = setInterval(_refreshCache, 120000)
    })

    onUnmounted(() => {
      if (_pollInterval) clearInterval(_pollInterval)
    })

    return {
      tempUnit, toDisplay, tempLabel,
      loading, polling, allServers, typeLabel, bmcTypeLabel, dash, alertedServers, alertLevel, alertReason, healthIssues, recentAlertLogs,
      powerHistory, powerEventClass,
      healthChartData, powerStateChartData, tempBarData, dashChartOptions, tempBarOptions,
      expandServer, collapseServer, jumpToServer, loadServerDetail, loadLogs, testConnection, powerAction,
      switchTab, loadHardware, loadNetwork, loadFirmware, loadSensors,
      showUpdateModal, updateOutput, updateRunning, updateSuccess, runUpdate,
      netEditForm, netSaving, startNetEdit, cancelNetEdit, saveNetwork,
      showBMCModal, bmcForm, bmcSaving, openConfigBMC, saveBMC, clearBMC,
      showStandaloneModal, standaloneForm, standaloneSaving, openAddStandalone, openEditStandalone, saveStandalone, deleteStandalone, deletePBS,
      showPBSModal, pbsForm, pbsSaving, openAddPBS, savePBS,
      pollNow,
      tempChartData, fanChartData, powerChartData,
      tempChartOptions, fanChartOptions, powerChartOptions,
      formatDate, formatRelative,
    }
  }
}
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: flex-start; }
.page-header h2 { margin: 0 0 0.25rem; }

/* Server card */
.server-card {
  background: var(--surface);
  border-radius: 0.5rem;
  box-shadow: var(--shadow);
  overflow: hidden;
}

.status-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1.25rem;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.status-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.status-right {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.srv-name {
  font-weight: 600;
  font-size: 0.9rem;
}

.type-pill {
  display: inline-block;
  font-size: 0.65rem;
  font-weight: 700;
  padding: 0.1rem 0.4rem;
  border-radius: 0.25rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.type-pill--pve { background: #dbeafe; color: #1e40af; }
.type-pill--pbs { background: #fef3c7; color: #92400e; }
.type-pill--standalone { background: #f3e8ff; color: #6b21a8; }

.power-badge, .health-badge {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.72rem;
  font-weight: 600;
}
.power-on { background: #dcfce7; color: #16a34a; }
.power-off { background: #fee2e2; color: #dc2626; }
.health-ok { background: #dcfce7; color: #16a34a; }
.health-warning { background: #fef9c3; color: #a16207; }
.health-critical { background: #fee2e2; color: #dc2626; }
.health-unknown { background: var(--background); color: var(--text-secondary); }

.error-inline { font-size: 0.72rem; color: #dc2626; font-weight: 600; }

.no-bmc-notice {
  padding: 0.5rem 1.25rem;
  font-size: 0.8rem;
  color: var(--text-secondary);
  background: var(--background);
  border-top: 1px solid var(--border-color);
}

/* Details panel */
.details-panel {
  border-top: 1px solid var(--border-color);
  padding: 0 1.25rem 1rem;
  position: relative;
}

/* Animated progress bar across the top of the details panel while loading */
.details-fetch-bar {
  height: 3px;
  background: var(--border-color);
  margin: 0 -1.25rem 0.75rem;
  overflow: hidden;
}
.details-fetch-bar__fill {
  height: 100%;
  width: 40%;
  background: var(--primary-color, #3b82f6);
  border-radius: 0 3px 3px 0;
  animation: fetch-slide 1.4s ease-in-out infinite;
}
@keyframes fetch-slide {
  0%   { transform: translateX(-100%); }
  60%  { transform: translateX(300%); }
  100% { transform: translateX(300%); }
}

.details-close {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 0.75rem;
}

.details-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 1.25rem;
}

.detail-section h4 {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  margin: 0 0 0.5rem;
}

.stat-list { display: flex; flex-direction: column; gap: 0.2rem; }
.stat-row {
  display: flex;
  justify-content: space-between;
  font-size: 0.82rem;
  padding: 0.2rem 0;
  border-bottom: 1px solid var(--border-color);
}
.stat-row span:first-child { color: var(--text-secondary); }
.stat-row span:last-child { font-family: monospace; font-size: 0.8rem; }
.bmc-link { font-family: monospace; font-size: 0.8rem; color: #3b82f6; text-decoration: underline; }
.bmc-link:hover { color: #60a5fa; }

.power-state-row { display: flex; align-items: center; gap: 0.5rem; }
.power-badge-lg, .health-badge-lg {
  padding: 0.2rem 0.6rem;
  border-radius: 9999px;
  font-size: 0.8rem;
  font-weight: 600;
}
.power-buttons { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.5rem; }

/* Charts */
.charts-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1rem;
}

.chart-section h4 {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  margin: 0 0 0.5rem;
}

.chart-wrapper {
  height: 180px;
  position: relative;
}

.chart-section--sm { max-width: 200px; }
.chart-wrapper--sm { height: 150px; }

/* Event log */
.log-table-wrapper {
  max-height: 250px;
  overflow-y: auto;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
}
.row-critical { background: #fff1f2; }
.row-warning { background: #fefce8; }

.details-loading {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem 0;
}

.error-box {
  padding: 0.6rem 1rem;
  background: #fee2e2;
  border: 1px solid #fca5a5;
  border-radius: 0.375rem;
  color: #dc2626;
  font-size: 0.82rem;
}

/* Modals */
.modal-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000;
}
.modal-content {
  background: var(--surface);
  border-radius: 0.5rem;
  width: 100%; max-width: 480px;
  box-shadow: var(--shadow-lg);
}
.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border-color);
}
.modal-header h3 { margin: 0; font-size: 1rem; }
.modal-close { background: none; border: none; font-size: 1.25rem; cursor: pointer; color: var(--text-secondary); line-height: 1; }
.modal-body { padding: 1rem 1.25rem; }
.modal-footer { display: flex; justify-content: flex-end; gap: 0.5rem; padding: 0.75rem 1.25rem; border-top: 1px solid var(--border-color); }

.text-xs { font-size: 0.75rem; }
.text-sm { font-size: 0.875rem; }
.text-muted { color: var(--text-secondary); }
.text-center { text-align: center; }
.mt-1 { margin-top: 0.5rem; }
.mt-2 { margin-top: 1rem; }
.mb-1 { margin-bottom: 0.5rem; }
.mb-2 { margin-bottom: 1rem; }
.p-3 { padding: 1.5rem; }

/* Tabs */
.detail-tabs {
  display: flex;
  gap: 0.25rem;
  margin-bottom: 1rem;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 0;
}
.tab-btn {
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  padding: 0.4rem 0.75rem;
  font-size: 0.82rem;
  font-weight: 500;
  cursor: pointer;
  color: var(--text-secondary);
  margin-bottom: -1px;
  transition: color 0.15s;
}
.tab-btn:hover { color: var(--text-primary); }
.tab-btn--active { color: var(--primary, #2563eb); border-bottom-color: var(--primary, #2563eb); font-weight: 600; }

/* Hardware tables */
.hw-table-wrapper {
  max-height: 300px;
  overflow-y: auto;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
}

/* Network */
.manager-banner {
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 0.5rem 0.75rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.net-iface-card {
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 0.75rem;
}
.net-iface-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.25rem;
}
.net-edit-form {
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 0.75rem;
}
.form-row { margin-bottom: 0.5rem; }
.form-row-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}
.form-control-sm { padding: 0.25rem 0.5rem; font-size: 0.8rem; }
.font-mono { font-family: monospace; }
.ml-1 { margin-left: 0.25rem; }

/* Update output */
.update-output {
  background: #0f172a;
  color: #e2e8f0;
  font-family: monospace;
  font-size: 0.75rem;
  line-height: 1.5;
  padding: 1rem;
  margin: 0;
  max-height: 500px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
.text-nowrap { white-space: nowrap; }

/* SSH toggle */
.ssh-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  cursor: pointer;
  padding: 0.15rem 0.5rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  user-select: none;
  background: var(--background);
}
.ssh-toggle input { cursor: pointer; }
.ssh-toggle span { font-weight: 600; color: var(--text-secondary); }

/* Dashboard */
.dashboard {
  background: var(--surface);
  border-radius: 0.5rem;
  box-shadow: var(--shadow);
  padding: 1rem 1.25rem;
}

.stat-cards {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.stat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 72px;
  padding: 0.6rem 1rem;
  border-radius: 0.4rem;
  background: var(--background);
  border: 1px solid var(--border-color);
}
.stat-card__value { font-size: 1.5rem; font-weight: 700; line-height: 1.2; }
.stat-card__label { font-size: 0.65rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-secondary); margin-top: 0.2rem; }

.stat-card--on  { border-color: #86efac; }
.stat-card--on .stat-card__value { color: #16a34a; }
.stat-card--ok  { border-color: #6ee7b7; }
.stat-card--ok .stat-card__value { color: #059669; }
.stat-card--warn { border-color: #fde68a; }
.stat-card--warn .stat-card__value { color: #d97706; }
.stat-card--crit { border-color: #fca5a5; }
.stat-card--crit .stat-card__value { color: #dc2626; }
.stat-card--err  { border-color: #fca5a5; }
.stat-card--err .stat-card__value { color: #dc2626; }
.stat-card--ssh  { border-color: #fde68a; }
.stat-card--ssh .stat-card__value { color: #92400e; }
.stat-card--muted { border-color: var(--border-color); }
.stat-card--muted .stat-card__value { color: var(--text-secondary); }

.alert-strip {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem;
  padding: 0.5rem 0.75rem;
  background: #fefce8;
  border: 1px solid #fde68a;
  border-radius: 0.375rem;
}
.alert-strip__label { font-size: 0.75rem; font-weight: 700; color: #92400e; margin-right: 0.25rem; }

.alert-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  cursor: pointer;
  border: none;
  font-family: inherit;
  padding: 0.1rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.72rem;
  font-weight: 600;
}
.alert-chip--crit { background: #fee2e2; color: #dc2626; }
.alert-chip--crit:hover { background: #fecaca; }
.alert-chip--warn { background: #fef9c3; color: #a16207; }
.alert-chip--warn:hover { background: #fef08a; }

/* ── Health issues panel ──────────────────────────────────────────────── */
.health-issues-panel {
  background: #1c1a14;
  border: 1px solid #a16207;
  border-radius: 0.5rem;
  padding: 0.75rem 1rem;
  margin-bottom: 1rem;
}
.health-issues-title {
  font-weight: 600;
  font-size: 0.85rem;
  color: #fbbf24;
  margin-bottom: 0.5rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.hi-badge {
  display: inline-block;
  padding: 0.1rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 700;
}
.hi-badge--crit { background: #dc2626; color: #fff; }
.hi-badge--warn { background: #d97706; color: #fff; }
.health-issues-list {
  list-style: none;
  margin: 0 0 0.5rem 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
.health-issues-list li {
  font-size: 0.82rem;
  padding: 0.3rem 0.6rem;
  border-radius: 0.25rem;
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
}
.hi-item--crit { background: rgba(220,38,38,0.15); color: #fca5a5; }
.hi-item--warn { background: rgba(217,119,6,0.15); color: #fcd34d; }
.hi-detail { opacity: 0.75; font-size: 0.78rem; }
.hi-tab-link {
  background: none; border: none; padding: 0; cursor: pointer;
  color: #60a5fa; text-decoration: underline; font-size: inherit; font-family: inherit;
}
.hi-tab-link:hover { color: #93c5fd; }
.hi-footer { margin-top: 0.5rem; border-top: 1px solid rgba(255,255,255,0.07); padding-top: 0.5rem; }
.hi-footer-title { font-size: 0.75rem; color: #94a3b8; margin-bottom: 0.3rem; }
.hi-log-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.hi-log-list li {
  font-size: 0.78rem;
  padding: 0.2rem 0.5rem;
  border-radius: 0.2rem;
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
}

.overview-table-wrap {
  overflow-x: auto;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
}
.table--compact th,
.table--compact td {
  padding: 0.3rem 0.6rem;
  font-size: 0.78rem;
}

/* Dashboard charts */
.dash-charts {
  display: grid;
  grid-template-columns: 140px 140px 1fr;
  gap: 0.75rem;
  align-items: start;
}

.dash-chart-card {
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 0.5rem;
}

.dash-chart-title {
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-secondary);
  margin-bottom: 0.4rem;
}

.dash-chart-wrap {
  height: 130px;
  position: relative;
}

.dash-chart-wrap--bar {
  height: 130px;
}

/* Temperature badge */
.temp-badge {
  display: inline-block;
  padding: 0.1rem 0.35rem;
  border-radius: 9999px;
  font-size: 0.7rem;
  font-weight: 600;
  font-family: monospace;
}
.temp-ok   { background: #dcfce7; color: #166534; }
.temp-warm { background: #fef9c3; color: #92400e; }
.temp-hot  { background: #fee2e2; color: #991b1b; }

@media (max-width: 640px) {
  .dash-charts { grid-template-columns: 1fr 1fr; }
  .dash-chart-card--wide { grid-column: 1 / -1; }
}

/* BMC type badge */
.type-pill--bmctype { background: #e0f2fe; color: #075985; }

/* Power history strip */
.power-history {
  border-top: 1px solid var(--border-color);
  padding-top: 0.75rem;
}
.power-history__title {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  margin-bottom: 0.4rem;
}
.power-history__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}
.power-history__item {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  font-size: 0.78rem;
  padding: 0.2rem 0.4rem;
  border-radius: 0.2rem;
  background: var(--background);
}
.power-history__badge {
  display: inline-block;
  padding: 0.05rem 0.35rem;
  border-radius: 9999px;
  font-size: 0.65rem;
  font-weight: 700;
  flex-shrink: 0;
}
.power-event--crit { background: #fee2e2; color: #dc2626; }
.power-event--warn { background: #fef9c3; color: #92400e; }
.power-event--info { background: #dbeafe; color: #1e40af; }

/* Sensor type pills */
.sensor-type-pill {
  display: inline-block;
  font-size: 0.65rem;
  font-weight: 600;
  padding: 0.05rem 0.35rem;
  border-radius: 0.2rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.sensor-type--temperature { background: #fee2e2; color: #991b1b; }
.sensor-type--fan { background: #dcfce7; color: #166534; }
.sensor-type--voltage { background: #fef9c3; color: #78350f; }
.sensor-type--power_supply { background: #dbeafe; color: #1e3a8a; }
</style>
