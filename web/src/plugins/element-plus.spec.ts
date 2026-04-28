import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import elementPlusPlugin from './element-plus'

describe('elementPlusPlugin', () => {
  it('registers shared components and loading directive for the app shell', () => {
    const wrapper = mount(
      {
        data: () => ({
          loading: false,
          rows: [{ name: 'alpha' }],
        }),
        template: `
          <el-container>
            <el-aside width="200px">
              <el-menu default-active="/dashboard">
                <el-menu-item index="/dashboard">概览</el-menu-item>
              </el-menu>
            </el-aside>
            <el-main>
              <el-form v-loading="loading">
                <el-form-item label="名称">
                  <el-input model-value="Quark STRM" />
                </el-form-item>
              </el-form>
              <el-button type="primary">保存</el-button>
              <el-table :data="rows">
                <el-table-column prop="name" label="名称" />
              </el-table>
              <el-tabs model-value="overview">
                <el-tab-pane label="概览" name="overview" />
              </el-tabs>
            </el-main>
          </el-container>
        `,
      },
      {
        global: {
          plugins: [elementPlusPlugin],
        },
      }
    )

    expect(wrapper.find('.el-button').exists()).toBe(true)
    expect(wrapper.find('.el-table').exists()).toBe(true)
    expect(wrapper.find('.el-tabs').exists()).toBe(true)
    expect(wrapper.find('.el-form').exists()).toBe(true)
  })
})
