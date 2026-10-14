<script setup lang="ts">
import type { ReportKind, ReportView } from "@/api/module_inventory/report/client";
import { Download, Refresh } from "@element-plus/icons-vue";
import { reportFilterQuery } from "../utils/query";
import { useReportTable } from "../composables/useReportTable";
import ReportFilters from "./ReportFilters.vue";
import ReportSummary from "./ReportSummary.vue";
import ReportSourceDetail from "./ReportSourceDetail.vue";
/** 固定领域和视图的报表内容，切换维度重新建立局部状态。 */
const props = defineProps<{ kind: ReportKind; view: ReportView }>();
const { hasAuth } = useAuth();
const {
  prefix,
  ready,
  authorized,
  form,
  summary,
  summaryLoading,
  summaryFailed,
  source,
  data,
  columns,
  columnChecks,
  loading,
  pagination,
  searchParams,
  error,
  onTableSelectionChange,
  exportConfig,
  exportVisible,
  exportDisabled,
  pageRows,
  selectionRows,
  loadSummary,
  search,
  reset,
  reload,
  changePage,
  changeSize,
  showExport,
} = useReportTable(props);
const showSearch = ref(true);
</script>
<template>
  <div class="fa-full-height">
    <ElResult v-if="!authorized" icon="warning" title="暂无报表查询权限" />
    <template v-else>
      <ReportFilters
        v-show="showSearch"
        v-model="form"
        :kind="kind"
        :view="view"
        :loading="loading"
        @search="search"
        @reset="reset"
      />
      <ReportSummary
        :kind="kind"
        :view="view"
        :value="summary"
        :loading="summaryLoading"
        :failed="summaryFailed"
        @retry="loadSummary"
      />
      <ElAlert
        v-if="!ready"
        class="mb-3"
        title="报表接口待接入"
        type="info"
        :closable="false"
        show-icon
      />
      <ElCard class="fa-table-card">
        <FaTableHeader
          v-model:columns="columnChecks"
          v-model:showSearchBar="showSearch"
          :loading="loading"
          @refresh="reload"
        >
          <template #left
            ><ElButton
              v-if="hasAuth(prefix + ':export')"
              type="warning"
              plain
              :icon="Download"
              :disabled="exportDisabled"
              @click="showExport"
              >导出</ElButton
            ></template
          >
        </FaTableHeader>
        <ElResult v-if="error && ready" icon="error" title="报表数据加载失败"
          ><template #extra
            ><ElButton :icon="Refresh" @click="reload">重试</ElButton></template
          ></ElResult
        >
        <FaTable
          v-else
          :data="data"
          :columns="columns"
          :loading="loading"
          :pagination="pagination"
          :empty-text="ready ? '暂无符合条件的数据' : '报表接口待接入'"
          @selection-change="onTableSelectionChange"
          @pagination:size-change="changeSize"
          @pagination:current-change="changePage"
        />
      </ElCard>
      <FaExportDialog
        v-model="exportVisible"
        :content-config="exportConfig"
        :query-params="reportFilterQuery(searchParams)"
        :page-data="pageRows"
        :selection-data="selectionRows"
      />
      <ReportSourceDetail v-model="source.visible" :row="source.row" />
    </template>
  </div>
</template>
