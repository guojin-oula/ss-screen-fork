<script>
  import { onMount } from 'svelte'
  import { Structure } from 'matterviz/structure'
  import { open_material } from 'matterviz/file-viewer/open'

  let structure = null
  let structureKey = 0
  let title = '请选择结构文件'
  let message = '支持 pymatgen JSON、POSCAR、CONTCAR、CIF 和 XYZ。'

  window.ssScreenLoadStructure = async (
	  content,
	  filename = 'structure.json',
	  label = filename
	) => {
	  try {
		const opened = await open_material({
		  data: content,
		  filename
		})

		if (opened.type === 'structure') {
		  structure = opened.data
		  structureKey += 1

		  title = label
		  message = ''
		} else {
		  structure = null
		  message = 'MatterViz 未能识别该结构。'
		}
	  } catch (error) {
		structure = null
		message = `结构加载失败：${error?.message ?? error}`
	  }
	}

  window.ssScreenClearStructure = () => {
    structure = null
    title = '请选择结构文件'
    message = '支持 pymatgen JSON、POSCAR、CONTCAR、CIF 和 XYZ。'
  }

  window.ssScreenMatterVizReady = true

  onMount(async () => {
    if (new URLSearchParams(window.location.search).get('demo') !== '1') return

    try {
      const response = await fetch('./demo-CaSe.json')
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      await window.ssScreenLoadStructure(
        await response.text(),
        'demo-CaSe.json',
        'CaSe 演示结构',
      )
    } catch (error) {
      message = `演示结构加载失败：${error?.message ?? error}`
    }
  })
</script>

<main>
  <header>
    <strong>{title}</strong>
    <span>MatterViz 0.7.0</span>
  </header>
  <section>
    {#if structure}
	  {#key structureKey}
		<Structure
		  {structure}
		  show_controls={false}
		  style="width: 100%; height: 100%;"
		/>
	  {/key}
	{:else}
      <div class="empty">{message}</div>
    {/if}
  </section>
</main>
