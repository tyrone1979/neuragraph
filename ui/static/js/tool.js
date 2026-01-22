let paramIdx = 0;
/* ===== 类型映射 ===== */
const typeTpl = {
  string:  () => `<input type="text" class="form-control form-control-sm" placeholder="string">`,
  number:  () => `<input type="number" class="form-control form-control-sm" placeholder="number" step="any">`,
  integer: () => `<input type="number" class="form-control form-control-sm" placeholder="integer" step="1">`,
  boolean: () => `<select class="form-select form-select-sm"><option value="">--</option><option value="true">true</option><option value="false">false</option></select>`,
  array:   () => `<textarea class="form-control form-control-sm" rows="1" placeholder='[item1, item2]'></textarea>`,
  object:  () => `<textarea class="form-control form-control-sm" rows="3" placeholder='{"key":"value"}'></textarea>`
};



if(existing.properties){
    Object.entries(existing.properties).forEach(([name,schema])=>{
      addParam();
      const card = $('#paramList > .card').last();
      card.find('.name').val(name);
      card.find('.type').val(schema.type).trigger('change');
      if('default' in schema){
        const dv = typeof schema.default === 'object' ? JSON.stringify(schema.default) : schema.default;
        card.find('.default-wrapper input, .default-wrapper select, .default-wrapper textarea').val(dv);
      }
      card.find('.desc').val(schema.description||'');
      card.find('.req').prop('checked', existing.required.includes(name));
    });
  }else{
    addParam(); // 至少一个空参数
}

$('#addParam').on('click', ()=>{
    addParam();
});

$('#back').on('click',()=>{
   history.back();
});

function collectForm(){
    const toolId   = $('#field_id').val().trim();
    const toolName = $('#field_name').val().trim();
    const toolDesc = $('#field_description').val().trim();
    const toolCode = $('#field_code').val();

    // 实时生成 parameters JSON
    const parameters = buildParamSchema();   // 返回 {type:'object',properties:{...},required:[...]}

    const toolDef = {
        id:          toolId,
        name:        toolName,
        description: toolDesc,
        parameters:  parameters,
        code:        toolCode
    };

    return toolDef;   // 漂亮格式化
}

function validateForm(){
    const toolId   = $('#field_id').val().trim();
    const toolName = $('#field_name').val().trim();
    const toolCode = $('#field_code').val();

    if (!toolId || !/^[a-zA-Z0-9_]+$/.test(toolId)) {
            alert('Invalid Tool ID: only letters, numbers, and underscores allowed');
            btn.prop('disabled', false).html('<i class="fas fa-save me-2"></i>Create');
            return false;
    }
    if (!toolName) {
            alert('Tool Name is required');
            btn.prop('disabled', false).html('<i class="fas fa-save me-2"></i>Create');
            return false;
    }
    if (!toolCode) {
            alert('Tool code is required');
            btn.prop('disabled', false).html('<i class="fas fa-save me-2"></i>Create');
            return false;
    }

    return true;
}


$('#saveToolBtn').on('click', function () {
    const btn = $(this);
    btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin me-2"></i>Saving...');
    saveToolForm();
    btn.prop('disabled', false).html(toolId ? '<i class="fas fa-save me-2"></i>Create' : '<i class="fas fa-save me-2"></i>Update');

});

$('#toolTestForm').on('click', function (e) {
    e.preventDefault();
   const $container = $('#resultContainer');
   const $loading = $('#loadingSpinner');
   const $output = $('#resultOutput');

   $container.removeClass('d-none');
   $loading.removeClass('d-none');
   $output.addClass('d-none').text('');

   const inputs = {};
   $(this).serializeArray().forEach(item => {
       let val = item.value.trim();
       if (val === '') return;

       // 尝试解析 JSON（对象或数组）
       if ((val.startsWith('{') && val.endsWith('}')) || (val.startsWith('[') && val.endsWith(']'))) {
           try {
               val = JSON.parse(val);
           } catch (e) {
               // 如果解析失败，保持原样（可能是普通长字符串）
               console.warn(`JSON parse failed for ${item.name}:`, e);
           }
       } else {
           // 简单类型转换
           if (val === 'true') val = true;
           else if (val === 'false') val = false;
           else if (!isNaN(val) && val !== '') val = Number(val);
       }

       inputs[item.name] = val;
   });

   $.ajax({
       url: '{{ url_for("tool.run_tool") }}',
       method: 'POST',
       contentType: 'application/json',
       data: JSON.stringify({ tool_id: "{{ tool_id }}", inputs: inputs }),
       success: function (res) {
           $loading.addClass('d-none');
           if (res.error) {
               $output.text('Error: ' + res.error).addClass('alert alert-danger').removeClass('bg-dark text-white');
           } else {
               $output.text(res.result || '(empty)');
           }
           $output.removeClass('d-none');
       },
       error: function (xhr) {
           $loading.addClass('d-none');
           const msg = xhr.responseJSON?.error || xhr.statusText;
           $output.text('Execution failed: ' + msg).addClass('alert alert-danger').removeClass('bg-dark text-white').removeClass('d-none');
       }
   });
});


function saveToolForm(){
    if(!validateForm()){
        return;
    }
    const toolId   = $('#field_id').val().trim();
    const toolDef=collectForm();

    $.ajax({
        url: '/tools/api/save_tool',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ tool_id: toolId, tool_def: toolDef }),
        success: function () {
            alert('Tool saved successfully!');
        },
        error: function (xhr) {
            alert('Save failed: ' + (xhr.responseJSON?.error || xhr.statusText));
        }
    });
}




function addParam(){
  const id = `p_${paramIdx++}`;
  $('#paramList').append(`
    <div class="card mb-2" id="${id}">
      <div class="card-header d-flex justify-content-between align-items-center px-2 py-1">
        <span class="fw-bold">Param ${paramIdx}</span>
        <button type="button" class="btn btn-sm btn-outline-danger" onclick="$('#${id}').remove();buildParamSchema();">
          <i class="fas fa-trash"></i>
        </button>
      </div>
      <div class="card-body px-2 py-2">
        <div class="row g-1">
          <div class="col-4"><label class="mb-0 fw-bold">Name</label><input type="text" class="form-control form-control-sm name" placeholder="paramName"></div>
          <div class="col-3"><label class="mb-0 fw-bold">Type</label><select class="form-select form-select-sm type" onchange="changeType('${id}')">${Object.keys(typeTpl).map(t=>`<option value="${t}">${t}</option>`).join('')}</select></div>
          <div class="col-5"><label class="mb-0 fw-bold">Default</label><div class="default-wrapper">${typeTpl.string()}</div></div>
        </div>
        <div class="mt-1"><label class="mb-0 fw-bold">Description</label><input type="text" class="form-control form-control-sm desc" placeholder="What this param does"></div>
        <div class="form-check mt-1"><input class="form-check-input req" type="checkbox"><label class="form-check-label">Required</label></div>
      </div>
    </div>
  `);

}

/* 类型切换 */
function changeType(cardId){
  const type = $(`#${cardId} .type`).val();
  $(`#${cardId} .default-wrapper`).html(typeTpl[type]());
  buildParamSchema();
}

/* 实时生成 parameters JSON */
function buildParamSchema(){
  const properties = {};
  const required   = [];
  $('#paramList > .card').each(function(){
    const name = $(this).find('.name').val().trim();
    if(!name) return;
    const type  = $(this).find('.type').val();
    const desc  = $(this).find('.desc').val().trim();
    const defVal= $(this).find('.default-wrapper input, .default-wrapper select, .default-wrapper textarea').val();
    const isReq = $(this).find('.req').is(':checked');

    properties[name] = { type, description: desc };
    /* 解析默认值（失败就留空）*/
    if(defVal !== ''){
      try{
        if(type === 'boolean') properties[name].default = defVal === 'true';
        else if(type === 'number' || type === 'integer') properties[name].default = Number(defVal);
        else if(type === 'object' || type === 'array') properties[name].default = JSON.parse(defVal);
        else properties[name].default = defVal;
      }catch(e){}
    }
    if(isReq) required.push(name);
  });
  return  { properties, required };
}