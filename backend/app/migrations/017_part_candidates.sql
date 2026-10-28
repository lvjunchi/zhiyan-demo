CREATE TABLE part_candidates (
 id TEXT PRIMARY KEY,
 model_code TEXT NOT NULL UNIQUE,
 part_name TEXT NOT NULL,
 rated_torque_nm REAL NOT NULL CHECK(rated_torque_nm>0),
 max_gears INTEGER NOT NULL CHECK(max_gears>0),
 material TEXT NOT NULL,
 image_key TEXT NOT NULL,
 source TEXT NOT NULL
);
INSERT INTO part_candidates VALUES ('06a1b3fa-3b32-5905-a81f-939d97bd2b43','DEMO-P01-1','主箱壳体',2400,8,'铸铁 / 常规包络','housing','合成候选库V1；额定扭矩/档数为演示匹配包络，非制造规格');
INSERT INTO part_candidates VALUES ('95b6fb9c-b8dc-54ae-b36d-ad44d4ba0675','DEMO-P01-2','主箱壳体',2600,12,'合金钢 / 标准包络','housing','合成候选库V1；额定扭矩/档数为演示匹配包络，非制造规格');
INSERT INTO part_candidates VALUES ('f899b705-79cc-57bd-9939-1b58509bfc0e','DEMO-P01-3','主箱壳体',3000,16,'合金钢 / 加强包络','housing','合成候选库V1；额定扭矩/档数为演示匹配包络，非制造规格');
INSERT INTO part_candidates VALUES ('af8403d6-d769-59be-97f8-93f00cd042a0','DEMO-P02-1','齿轮组',2400,8,'铸铁 / 常规包络','gear','合成候选库V1；额定扭矩/档数为演示匹配包络，非制造规格');
INSERT INTO part_candidates VALUES ('77f3a508-bdc8-5e93-b6c5-bfff98919a1f','DEMO-P02-2','齿轮组',2600,12,'合金钢 / 标准包络','gear','合成候选库V1；额定扭矩/档数为演示匹配包络，非制造规格');
INSERT INTO part_candidates VALUES ('20afda6b-a165-5866-81ea-16f13ed1527b','DEMO-P02-3','齿轮组',3000,16,'合金钢 / 加强包络','gear','合成候选库V1；额定扭矩/档数为演示匹配包络，非制造规格');
INSERT INTO part_candidates VALUES ('f9e74bec-a94d-592a-a5f6-64abca0f884c','DEMO-P03-1','一轴齿轮',2400,8,'铸铁 / 常规包络','gear','合成候选库V1；额定扭矩/档数为演示匹配包络，非制造规格');
INSERT INTO part_candidates VALUES ('e6402ca6-8e95-519b-bff7-94604987b25a','DEMO-P03-2','一轴齿轮',2600,12,'合金钢 / 标准包络','gear','合成候选库V1；额定扭矩/档数为演示匹配包络，非制造规格');
INSERT INTO part_candidates VALUES ('27f6f4bc-a9bd-5230-8b8c-baf6233c25af','DEMO-P03-3','一轴齿轮',3000,16,'合金钢 / 加强包络','gear','合成候选库V1；额定扭矩/档数为演示匹配包络，非制造规格');
INSERT INTO part_candidates VALUES ('d390d0f9-cc05-5ccd-9a79-91b590cfd702','DEMO-P04-1','输入轴',2400,8,'铸铁 / 常规包络','shaft','合成候选库V1；额定扭矩/档数为演示匹配包络，非制造规格');
INSERT INTO part_candidates VALUES ('1b92cf04-948b-5ec4-b2fe-323b23d539e2','DEMO-P04-2','输入轴',2600,12,'合金钢 / 标准包络','shaft','合成候选库V1；额定扭矩/档数为演示匹配包络，非制造规格');
INSERT INTO part_candidates VALUES ('c860aba9-1347-5548-aeb0-ae19e6600529','DEMO-P04-3','输入轴',3000,16,'合金钢 / 加强包络','shaft','合成候选库V1；额定扭矩/档数为演示匹配包络，非制造规格');
INSERT INTO part_candidates VALUES ('9f5a86d4-cceb-51c7-ad90-3ef98eafd805','DEMO-P05-1','离合器壳',2400,8,'铸铁 / 常规包络','housing','合成候选库V1；额定扭矩/档数为演示匹配包络，非制造规格');
INSERT INTO part_candidates VALUES ('69a51015-e197-5b9b-921f-e803c99f1050','DEMO-P05-2','离合器壳',2600,12,'合金钢 / 标准包络','housing','合成候选库V1；额定扭矩/档数为演示匹配包络，非制造规格');
INSERT INTO part_candidates VALUES ('2545d18e-37aa-5a1a-955a-3a783c5a2da5','DEMO-P05-3','离合器壳',3000,16,'合金钢 / 加强包络','housing','合成候选库V1；额定扭矩/档数为演示匹配包络，非制造规格');
INSERT INTO part_candidates VALUES ('a0856858-0b2a-5b6b-8427-2d72dc948abc','DEMO-P06-1','输出法兰',2400,8,'铸铁 / 常规包络','flange','合成候选库V1；额定扭矩/档数为演示匹配包络，非制造规格');
INSERT INTO part_candidates VALUES ('69271ba8-de16-5078-9d75-3009067659f6','DEMO-P06-2','输出法兰',2600,12,'合金钢 / 标准包络','flange','合成候选库V1；额定扭矩/档数为演示匹配包络，非制造规格');
INSERT INTO part_candidates VALUES ('66d55ac1-d116-52b6-b98b-7c0f0e9cbc25','DEMO-P06-3','输出法兰',3000,16,'合金钢 / 加强包络','flange','合成候选库V1；额定扭矩/档数为演示匹配包络，非制造规格');
INSERT INTO part_candidates VALUES ('acd38018-b24d-5e09-9382-711cf9c0c234','DEMO-P07-1','换挡执行机构',2400,8,'铸铁 / 常规包络','actuator','合成候选库V1；额定扭矩/档数为演示匹配包络，非制造规格');
INSERT INTO part_candidates VALUES ('6117630c-cb31-5f95-83be-d740d507d322','DEMO-P07-2','换挡执行机构',2600,12,'合金钢 / 标准包络','actuator','合成候选库V1；额定扭矩/档数为演示匹配包络，非制造规格');
INSERT INTO part_candidates VALUES ('c269fd4c-a108-5921-9f8d-21593d474384','DEMO-P07-3','换挡执行机构',3000,16,'合金钢 / 加强包络','actuator','合成候选库V1；额定扭矩/档数为演示匹配包络，非制造规格');
INSERT INTO part_candidates VALUES ('2e2134b7-0aa8-5c86-927d-f189ab75d1b7','DEMO-P08-1','取力器接口',2400,8,'铸铁 / 常规包络','flange','合成候选库V1；额定扭矩/档数为演示匹配包络，非制造规格');
INSERT INTO part_candidates VALUES ('ba2ce6ea-4598-5fb4-a0f9-9dbf841302c8','DEMO-P08-2','取力器接口',2600,12,'合金钢 / 标准包络','flange','合成候选库V1；额定扭矩/档数为演示匹配包络，非制造规格');
INSERT INTO part_candidates VALUES ('9fb42a8e-04a4-5177-9050-7053b6ea561c','DEMO-P08-3','取力器接口',3000,16,'合金钢 / 加强包络','flange','合成候选库V1；额定扭矩/档数为演示匹配包络，非制造规格');
CREATE TRIGGER part_candidates_immutable_update BEFORE UPDATE ON part_candidates
BEGIN SELECT RAISE(ABORT, 'controlled candidate catalog is read only'); END;
CREATE TRIGGER part_candidates_immutable_delete BEFORE DELETE ON part_candidates
BEGIN SELECT RAISE(ABORT, 'controlled candidate catalog is read only'); END;
