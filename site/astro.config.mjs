import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://huangchiyu.com',
  base: '/Workflow-skill-router',
  integrations: [
    starlight({
      title: 'Workflow Skill Router',
      description: 'A practical routing pattern for multi-skill AI agents.',
      defaultLocale: 'root',
      locales: {
        root: {
          label: 'English',
          lang: 'en',
        },
        'zh-tw': {
          label: '繁體中文',
          lang: 'zh-TW',
        },
      },
      logo: {
        light: './src/assets/routing-mark-light.svg',
        dark: './src/assets/routing-mark-dark.svg',
      },
      social: [
        {
          icon: 'github',
          label: 'GitHub',
          href: 'https://github.com/eric861129/Workflow-skill-router',
        },
      ],
      customCss: ['./src/styles/custom.css'],
      sidebar: [
        {
          label: 'Start Here',
          translations: {
            'zh-TW': '開始使用',
          },
          items: [
            { slug: '' },
            { slug: 'guides/quickstart' },
            { slug: 'guides/downloads' },
            { slug: 'guides/adoption' },
          ],
        },
        {
          label: 'Examples',
          translations: {
            'zh-TW': '範例',
          },
          items: [
            { slug: 'examples/common-engineering' },
            { slug: 'examples/company-platform' },
            { slug: 'examples/frontend-debugging' },
          ],
        },
        {
          label: 'Reference',
          translations: {
            'zh-TW': '參考資料',
          },
          items: [
            { slug: 'reference/routing-contract' },
            { slug: 'reference/validator' },
            { slug: 'reference/sample-skills' },
            { slug: 'reference/source-map' },
          ],
        },
      ],
    }),
  ],
});
