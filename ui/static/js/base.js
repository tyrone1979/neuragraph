$(document).ready(function() {

  const detailsData = {{ details|tojson }};
  const mealPlan =    {{ meal_plan|tojson }};
  const targetRange = {{ target_range|tojson }};
  const targetData =  {{ target|tojson }};
  render(targetRange,targetData,mealPlan,detailsData)
});