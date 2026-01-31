// 注册单位映射过滤器
function getUnit(nutrient) {
  const units = {
    cholesterol: "mg",
    calorie: "kcal",
    saturated_fat: "g"
  };
  return units[nutrient] || "g"; // 默认单位为克
}


function fetchUsers(filter) {
        fetch(`/fetch-users?filter=${filter}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const userList = document.getElementById('user-list');
                    userList.innerHTML = ''; // 清空当前用户列表
                    data.users.forEach(user => {
                        const row = document.createElement('tr');
                        row.innerHTML = `
                            <td>${user.user_id}</td>
                            <td>${user.age}</td>
                            <td>${user.gender === 1 ? 'Male' : user.gender === 2 ? 'Female' : ''}</td>
                            <td>${user.weight}</td>
                            <td>${user.height}</td>
                            <td>
                                ${Object.keys(user).filter(key => ['under_weight', 'over_weight', 'opioid_misuse', 'low_density_lipoprotein',
                                    'blood_urea_nitrogen', 'blood_pressure', 'diabetes', 'anemia', 'osteoporosis'].includes(key) && user[key] === 1)
                                    .map(attr => `<span class="tag tag-${attr}">${attr.replace(/_/g, ' ')}</span>`).join('')}
                            </td>
                            <td>
                                ${Object.keys(user).filter(key => key.startsWith('user_') && user[key] === 1)
                                    .map(attr => `<span class="tag tag-${attr.slice(5)}">${attr.slice(5).replace(/_/g, ' ')}</span>`).join('')}
                            </td>
                            <td id="target-${user.user_id}" class="nutrition-targets">
                                <!-- 留空，由JavaScript填充 -->
                            </td>
                            <td><a href="javascript:void(0);" class="btn btn-sm btn-outline-success meal-plan-btn border-0 p-1 text-nowrap"
                                    data-id="${user.user_id}" role="button">${user.meal_plan_count}</a></td>
                        `;
                        userList.appendChild(row);
                    });
                } else {
                    alert('Failed to load users: ' + data.message);
                }
            })
            .catch(error => {
                console.error('Error fetching users:', error);
                alert('Failed to load users.');
            });
    }